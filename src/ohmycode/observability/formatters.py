"""OTel ConsoleExporter 的自定义格式化器。

将 span/metric 输出格式化为可读的终端格式，兼容 Rich 渲染。
"""

import json
import sys
from datetime import datetime, timezone
from typing import Any


def format_span_for_console(span: Any) -> str:
    """将 Span 格式化为可读的控制台输出。

    Args:
        span: OTel Span 对象或 ReadableSpan

    Returns:
        格式化后的字符串
    """
    context = span.get_span_context()
    trace_id = format(context.trace_id, "032x")
    span_id = format(context.span_id, "016x")

    # 截断显示
    short_trace = trace_id[:8] + "..." + trace_id[-4:]
    short_span = span_id[:8]

    name = span.name
    kind = str(span.kind).split(".")[-1] if span.kind else "INTERNAL"

    start_time = span.start_time
    end_time = span.end_time
    if start_time and end_time:
        duration_ns = end_time - start_time
        duration_ms = duration_ns / 1_000_000
        duration_str = f"{duration_ms:.1f}ms"
    else:
        duration_str = "N/A"

    status = str(span.status.status_code).split(".")[-1] if span.status else "UNSET"

    parts = [
        f"[dim][{kind}][/]",
        f"[bold cyan]{name}[/]",
        f"trace={short_trace}",
        f"span={short_span}",
        f"{duration_str}",
        f"[{status}]",
    ]

    # 添加 attributes 摘要
    if span.attributes:
        attr_items = []
        for k, v in list(span.attributes.items())[:5]:  # 最多显示 5 个
            attr_items.append(f"{k}={v}")
        if attr_items:
            parts.append("[" + ", ".join(attr_items) + "]")

    return " ".join(parts)


def format_metric_for_console(
    instrument_name: str,
    value: Any,
    attributes: dict[str, str] | None = None,
) -> str:
    """将 Metric 数据点格式化为可读的控制台输出。

    Args:
        instrument_name: 指标名称
        value: 指标值
        attributes: 指标属性/标签

    Returns:
        格式化后的字符串
    """
    timestamp = datetime.now(tz=timezone.utc).strftime("%H:%M:%S")
    parts = [
        f"[dim][{timestamp}][/]",
        f"[bold green]{instrument_name}[/]",
        f"= {value}",
    ]
    if attributes:
        labels = ", ".join(f"{k}={v}" for k, v in attributes.items())
        parts.append(f"{{{labels}}}")

    return " ".join(parts)


def format_log_record(
    name: str,
    level: str,
    message: str,
    trace_id: str | None = None,
    span_id: str | None = None,
    extra: dict[str, Any] | None = None,
) -> str:
    """将日志记录格式化为结构化输出。

    Args:
        name: Logger 名称
        level: 日志级别
        message: 日志消息
        trace_id: 追踪 ID（可选）
        span_id: Span ID（可选）
        extra: 额外的结构化字段

    Returns:
        格式化后的日志字符串
    """
    timestamp = datetime.now(tz=timezone.utcnow).strftime("%Y-%m-%d %H:%M:%S")

    parts = [f"[dim]{timestamp}[/]", f"[{level}]{level:<8}[/]", f"[{name}]"]

    if trace_id:
        short = trace_id[:8] + "..." + trace_id[-4:]
        parts.append(f"[dim]trace={short}[/]")
    if span_id:
        parts.append(f"[dim]span={span_id[:8]}[/]")

    parts.append(message)

    if extra:
        extra_str = json.dumps(extra, default=str, ensure_ascii=False)
        parts.append(f"[dim]{extra_str}[/]")

    return " ".join(parts)
