"""结构化日志工厂。

提供 get_logger(name) 工厂函数，返回自动注入 trace_id/span_id 的 Logger 实例。
使用 Python 标准 logging 模块，兼容 Rich Handler 格式化。
"""

import logging
import sys
from typing import Any

from opentelemetry import trace

# 模块级 Logger 缓存
_loggers: dict[str, logging.Logger] = {}


class TraceContextFilter(logging.Filter):
    """日志过滤器：自动注入当前 OTel trace_id 和 span_id。

    将 otelTraceID 和 otelSpanID 附加到每条日志记录，
    便于在结构化日志中关联 Trace 信息。
    """

    def filter(self, record: logging.LogRecord) -> bool:
        """为日志记录注入 OTel 上下文。"""
        # 获取当前 span 上下文
        current_span = trace.get_current_span()
        span_context = current_span.get_span_context()

        if span_context and span_context.is_valid:
            record.otelTraceID = format(span_context.trace_id, "032x")
            record.otelSpanID = format(span_context.span_id, "016x")
        else:
            record.otelTraceID = "0" * 32
            record.otelSpanID = "0" * 16

        return True


def get_logger(name: str) -> logging.Logger:
    """获取自动注入 trace_id/span_id 的结构化 Logger。

    所有模块应通过此函数获取 Logger：
        logger = get_logger(__name__)

    Logger 自动携带 OTel 上下文信息。

    Args:
        name: Logger 名称，通常使用 __name__

    Returns:
        配置好的 Logger 实例
    """
    if name in _loggers:
        return _loggers[name]

    logger = logging.getLogger(name)

    # 避免重复添加 Filter
    has_trace_filter = any(
        isinstance(f, TraceContextFilter) for f in logger.filters
    )
    if not has_trace_filter:
        logger.addFilter(TraceContextFilter())

    _loggers[name] = logger
    return logger


def setup_logging(level: str = "INFO") -> None:
    """初始化全局日志配置。

    应在应用启动时调用。配置 ohmycode 命名空间下的所有 Logger。

    Args:
        level: 日志级别（DEBUG/INFO/WARNING/ERROR）
    """
    log_level = getattr(logging, level.upper(), logging.INFO)

    # 配置 ohmycode 根 Logger
    root_logger = logging.getLogger("ohmycode")
    root_logger.setLevel(log_level)

    # 添加带 TraceContextFilter 的 Handler（仅当没有 handler 时）
    if not root_logger.handlers:
        handler = logging.StreamHandler(sys.stderr)
        handler.setLevel(log_level)
        handler.addFilter(TraceContextFilter())

        formatter = logging.Formatter(
            "%(asctime)s [%(levelname)s] %(name)s "
            "trace_id=%(otelTraceID)s span_id=%(otelSpanID)s "
            "%(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
        handler.setFormatter(formatter)
        root_logger.addHandler(handler)
