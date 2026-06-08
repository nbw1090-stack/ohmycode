"""OpenTelemetry Metrics 工具函数。

提供全局 get_meter() 便捷函数，以及预定义的 Counter 和 Histogram 指标。
所有指标通过 MeterProvider 收集，默认使用 ConsoleMetricExporter 输出到 stderr。
"""

from typing import Any

from opentelemetry import metrics
from opentelemetry.metrics import Counter, Histogram, Meter

# ===== 指标名称常量 =====

# Token 用量计数器
METER_NAME = "ohmycode"

# LLM Token 用量
TOKEN_COUNTER_NAME = "ohmycode.llm.tokens"
LLM_DURATION_NAME = "ohmycode.llm.duration"

# 工具调用
TOOL_CALL_COUNTER_NAME = "ohmycode.tools.calls"
TOOL_DURATION_NAME = "ohmycode.tools.duration"
TOOL_ERROR_COUNTER_NAME = "ohmycode.tools.errors"

# 对话级别
CONVERSATION_DURATION_NAME = "ohmycode.conversation.duration"

# 全局错误
ERROR_COUNTER_NAME = "ohmycode.errors"

# 模块级缓存（注意：不缓存 Meter，每次从 MeterProvider 获取）
_token_counter: Counter | None = None
_llm_duration: Histogram | None = None
_tool_call_counter: Counter | None = None
_tool_duration: Histogram | None = None
_tool_error_counter: Counter | None = None
_conversation_duration: Histogram | None = None
_error_counter: Counter | None = None


def get_meter(name: str = METER_NAME) -> Meter:
    """获取 OTel Meter 实例。

    每次都从全局 MeterProvider 获取最新 Meter，
    确保在测试中切换 MeterProvider 后不会使用缓存的旧 Meter。

    Args:
        name: Meter 名称

    Returns:
        OTel Meter 实例
    """
    return metrics.get_meter(name)


def get_token_counter() -> Counter:
    """获取 LLM Token 用量计数器。

    按 model 标签区分不同模型的 Token 用量。

    Returns:
        Counter 实例
    """
    global _token_counter
    if _token_counter is None:
        _token_counter = get_meter().create_counter(
            name=TOKEN_COUNTER_NAME,
            description="LLM Token 用量总计",
            unit="tokens",
        )
    return _token_counter


def get_llm_duration() -> Histogram:
    """获取 LLM 调用延迟直方图。

    按 model 标签区分不同模型的调用延迟。

    Returns:
        Histogram 实例
    """
    global _llm_duration
    if _llm_duration is None:
        _llm_duration = get_meter().create_histogram(
            name=LLM_DURATION_NAME,
            description="LLM 调用延迟",
            unit="ms",
        )
    return _llm_duration


def get_tool_call_counter() -> Counter:
    """获取工具调用频次计数器。

    按 tool_name 标签区分不同工具的调用次数。

    Returns:
        Counter 实例
    """
    global _tool_call_counter
    if _tool_call_counter is None:
        _tool_call_counter = get_meter().create_counter(
            name=TOOL_CALL_COUNTER_NAME,
            description="工具调用频次",
            unit="calls",
        )
    return _tool_call_counter


def get_tool_duration() -> Histogram:
    """获取工具执行延迟直方图。

    按 tool_name 标签区分不同工具的执行延迟。

    Returns:
        Histogram 实例
    """
    global _tool_duration
    if _tool_duration is None:
        _tool_duration = get_meter().create_histogram(
            name=TOOL_DURATION_NAME,
            description="工具执行延迟",
            unit="ms",
        )
    return _tool_duration


def get_tool_error_counter() -> Counter:
    """获取工具调用错误计数器。

    按 tool_name 和 error_type 标签区分错误类型。

    Returns:
        Counter 实例
    """
    global _tool_error_counter
    if _tool_error_counter is None:
        _tool_error_counter = get_meter().create_counter(
            name=TOOL_ERROR_COUNTER_NAME,
            description="工具调用错误数",
            unit="errors",
        )
    return _tool_error_counter


def get_conversation_duration() -> Histogram:
    """获取对话完整延迟直方图。

    记录从用户输入到 Agent 回复完成的总时间。

    Returns:
        Histogram 实例
    """
    global _conversation_duration
    if _conversation_duration is None:
        _conversation_duration = get_meter().create_histogram(
            name=CONVERSATION_DURATION_NAME,
            description="对话完整延迟（用户输入到回复完成）",
            unit="ms",
        )
    return _conversation_duration


def get_error_counter() -> Counter:
    """获取全局错误计数器。

    按 module 和 error_type 标签区分错误来源和类型。

    Returns:
        Counter 实例
    """
    global _error_counter
    if _error_counter is None:
        _error_counter = get_meter().create_counter(
            name=ERROR_COUNTER_NAME,
            description="全局错误计数",
            unit="errors",
        )
    return _error_counter


def reset_metrics() -> None:
    """重置所有缓存的指标实例。

    主要用于测试场景，清理单例状态。
    下次调用 getter 时会从当前 MeterProvider 重新创建。
    """
    global _token_counter, _llm_duration
    global _tool_call_counter, _tool_duration, _tool_error_counter
    global _conversation_duration, _error_counter

    _token_counter = None
    _llm_duration = None
    _tool_call_counter = None
    _tool_duration = None
    _tool_error_counter = None
    _conversation_duration = None
    _error_counter = None


def record_token_usage(
    *,
    model: str,
    prompt_tokens: int,
    completion_tokens: int,
    total_tokens: int,
) -> None:
    """记录 LLM Token 用量。

    便捷函数：同时记录 prompt/completion/total Token 计数。

    Args:
        model: 模型名称
        prompt_tokens: 输入 Token 数
        completion_tokens: 输出 Token 数
        total_tokens: 总 Token 数
    """
    counter = get_token_counter()
    labels = {"model": model}

    counter.add(prompt_tokens, attributes={**labels, "token_type": "prompt"})
    counter.add(completion_tokens, attributes={**labels, "token_type": "completion"})
    counter.add(total_tokens, attributes={**labels, "token_type": "total"})


def record_tool_call(
    *,
    tool_name: str,
    duration_ms: float,
    error: str | None = None,
) -> None:
    """记录工具调用指标。

    便捷函数：同时记录调用计数、延迟和错误（如有）。

    Args:
        tool_name: 工具名称
        duration_ms: 执行耗时（毫秒）
        error: 错误类型（可选，无错误为 None）
    """
    labels = {"tool_name": tool_name}

    # 调用计数
    get_tool_call_counter().add(1, attributes=labels)

    # 延迟
    get_tool_duration().record(duration_ms, attributes=labels)

    # 错误计数
    if error:
        get_tool_error_counter().add(
            1,
            attributes={**labels, "error_type": error},
        )


def record_error(
    *,
    module: str,
    error_type: str,
) -> None:
    """记录全局错误指标。

    Args:
        module: 错误来源模块（agent/llm/tools/tui）
        error_type: 错误类型
    """
    get_error_counter().add(
        1,
        attributes={"module": module, "error_type": error_type},
    )
