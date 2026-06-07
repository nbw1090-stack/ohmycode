"""OpenTelemetry Tracing 工具函数。

提供全局 get_tracer() 便捷函数，以及用于创建 span 的上下文管理器和辅助函数。
"""

import asyncio
import functools
import time
from contextlib import contextmanager
from typing import Any, Callable, Generator, TypeVar

from opentelemetry import trace
from opentelemetry.trace import Span, SpanKind, Tracer

from ohmycode.observability.spans import (
    ATTR_COMPLETION_TOKENS,
    ATTR_CONVERSATION_ID,
    ATTR_DECISION,
    ATTR_ERROR_MESSAGE,
    ATTR_ERROR_TYPE,
    ATTR_MODEL,
    ATTR_PROMPT_TOKENS,
    ATTR_TOTAL_TOKENS,
    ATTR_TOOL_ARGS,
    ATTR_TOOL_NAME,
    EVENT_ERROR,
    EVENT_ROUTING_DECISION,
)

# 模块级 Tracer 缓存
_tracer: Tracer | None = None

# 默认 Tracer 名称
_TRACER_NAME = "ohmycode"


def get_tracer(name: str = _TRACER_NAME) -> Tracer:
    """获取 OTel Tracer 实例。

    如果 OTel 未初始化，返回一个无操作的 Tracer（不会报错）。

    Args:
        name: Tracer 名称，通常为模块名

    Returns:
        OTel Tracer 实例
    """
    global _tracer
    if _tracer is None:
        _tracer = trace.get_tracer(name)
    return _tracer


@contextmanager
def span(
    name: str,
    *,
    kind: SpanKind = SpanKind.INTERNAL,
    attributes: dict[str, Any] | None = None,
) -> Generator[Span, None, None]:
    """创建一个 OTel Span 的上下文管理器。

    用法::

        with span("ohmycode.agent.call_model", attributes={"model": "gpt-4o"}) as s:
            result = do_something()
            s.set_attribute("result_length", len(result))

    Args:
        name: Span 名称
        kind: Span 类型（INTERNAL/SERVER/CLIENT/PRODUCER/CONSUMER）
        attributes: 初始 Span 属性

    Yields:
        活跃的 Span 对象
    """
    tracer = get_tracer()
    with tracer.start_as_current_span(name, kind=kind, attributes=attributes) as s:
        try:
            yield s
        except Exception as exc:
            # 记录异常到 Span
            s.set_status(trace.StatusCode.ERROR, str(exc))
            s.record_exception(exc)
            s.add_event(
                EVENT_ERROR,
                {
                    ATTR_ERROR_TYPE: type(exc).__name__,
                    ATTR_ERROR_MESSAGE: str(exc),
                },
            )
            raise


def trace_conversation(conversation_id: str) -> Span:
    """创建一个对话级别的 Trace（根 Span）。

    用于追踪从用户输入到 Agent 回复完成的完整生命周期。

    Args:
        conversation_id: 对话唯一标识

    Returns:
        新创建的 Span
    """
    tracer = get_tracer()
    return tracer.start_span(
        "ohmycode.conversation",
        kind=SpanKind.SERVER,
        attributes={
            ATTR_CONVERSATION_ID: conversation_id,
        },
    )


def record_token_usage(
    s: Span,
    *,
    model: str,
    prompt_tokens: int,
    completion_tokens: int,
    total_tokens: int,
) -> None:
    """在 Span 上记录 LLM Token 用量。

    Args:
        s: 目标 Span
        model: 模型名称
        prompt_tokens: 输入 Token 数
        completion_tokens: 输出 Token 数
        total_tokens: 总 Token 数
    """
    s.set_attribute(ATTR_MODEL, model)
    s.set_attribute(ATTR_PROMPT_TOKENS, prompt_tokens)
    s.set_attribute(ATTR_COMPLETION_TOKENS, completion_tokens)
    s.set_attribute(ATTR_TOTAL_TOKENS, total_tokens)


def record_routing_decision(s: Span, decision: str) -> None:
    """在 Span 上记录路由决策事件。

    Args:
        s: 目标 Span
        decision: 路由决策（"tools" 或 "__end__"）
    """
    s.add_event(EVENT_ROUTING_DECISION, {ATTR_DECISION: decision})


def record_tool_call(
    s: Span,
    *,
    tool_name: str,
    args_summary: str = "",
) -> None:
    """在 Span 上记录工具调用信息。

    Args:
        s: 目标 Span
        tool_name: 工具名称
        args_summary: 参数摘要（注意不要记录敏感信息）
    """
    s.set_attribute(ATTR_TOOL_NAME, tool_name)
    if args_summary:
        s.set_attribute(ATTR_TOOL_ARGS, args_summary)


F = TypeVar("F", bound=Callable[..., Any])


def traced(
    name: str,
    *,
    kind: SpanKind = SpanKind.INTERNAL,
    attributes: dict[str, Any] | None = None,
) -> Callable[[F], F]:
    """装饰器：将函数包裹在 OTel Span 中。

    用法::

        @traced("ohmycode.agent.call_model")
        async def call_model(state):
            ...

    Args:
        name: Span 名称
        kind: Span 类型
        attributes: 初始 Span 属性

    Returns:
        装饰后的函数
    """

    def decorator(func: F) -> F:
        if asyncio.iscoroutinefunction(func):

            @functools.wraps(func)
            async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
                with span(name, kind=kind, attributes=attributes):
                    return await func(*args, **kwargs)

            return async_wrapper  # type: ignore[return-value]
        else:

            @functools.wraps(func)
            def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
                with span(name, kind=kind, attributes=attributes):
                    return func(*args, **kwargs)

            return sync_wrapper  # type: ignore[return-value]

    return decorator
