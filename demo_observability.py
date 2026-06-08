"""可观测性演示脚本 — 展示 Tracing、Metrics、Logging 三大支柱。

用法: python demo_observability.py

不启动 TUI，直接在终端输出 OTel 数据，清晰展示：
1. 分布式追踪（Span 层级、属性、事件）
2. 指标收集（Counter、Histogram）
3. 结构化日志（自动注入 trace_id / span_id）
"""

import time
import uuid

from opentelemetry import metrics, trace
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import (
    ConsoleMetricExporter,
    PeriodicExportingMetricReader,
)
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import ConsoleSpanExporter, SimpleSpanProcessor

# ─── 1. 初始化 OTel（等同于 DefaultObservabilityProvider.setup()）───

print("=" * 70)
print("🔧 初始化 OpenTelemetry 可观测性系统")
print("=" * 70)

resource = Resource.create(
    {"service.name": "ohmycode", "service.version": "0.1.0"}
)

# Tracing — ConsoleSpanExporter 输出到 stdout（演示用）
tracer_provider = TracerProvider(resource=resource)
span_exporter = ConsoleSpanExporter()  # 默认输出到 stdout
tracer_provider.add_span_processor(SimpleSpanProcessor(span_exporter))
trace.set_tracer_provider(tracer_provider)

# Metrics — ConsoleMetricExporter
metric_reader = PeriodicExportingMetricReader(
    exporter=ConsoleMetricExporter(),
    export_interval_millis=2_000,  # 每 2 秒输出一次指标
)
meter_provider = MeterProvider(resource=resource, metric_readers=[metric_reader])
metrics.set_meter_provider(meter_provider)

# 初始化结构化日志（带 trace_id/span_id 注入）
from ohmycode.observability.logging import setup_logging, get_logger

setup_logging(level="DEBUG")
logger = get_logger("ohmycode.demo")


# ─── 2. 模拟一次完整的 Agent 对话流程 ───

print("\n" + "=" * 70)
print("📋 模拟 Agent 对话流程（Tracing + Metrics + Logging）")
print("=" * 70 + "\n")

# 获取 Tracer 和 Meter
from ohmycode.observability.tracing import (
    get_tracer,
    span,
    trace_conversation,
    record_token_usage as trace_record_token,
    record_routing_decision,
    record_tool_call as trace_record_tool_call,
)
from ohmycode.observability.metrics import (
    get_token_counter,
    get_llm_duration,
    get_tool_call_counter,
    get_tool_duration,
    get_conversation_duration,
    record_token_usage,
    record_tool_call,
    record_error,
)

tracer = get_tracer()
conversation_id = str(uuid.uuid4())[:8]

# ─── 根 Span: 对话级别 ───
with span(
    "ohmycode.conversation",
    kind=trace.SpanKind.SERVER,
    attributes={"conversation.id": conversation_id},
) as conv_span:
    logger.info("开始对话 conversation_id=%s", conversation_id)
    start_time = time.time()

    # ─── 子 Span 1: Agent 调用模型 ───
    with span(
        "ohmycode.agent.call_model",
        attributes={"llm.model": "gpt-4o"},
    ) as model_span:
        logger.info("调用 LLM 模型 gpt-4o")

        # 模拟 LLM 调用延迟
        time.sleep(0.3)

        # 记录 Token 用量（Tracing）
        trace_record_token(
            model_span,
            model="gpt-4o",
            prompt_tokens=256,
            completion_tokens=128,
            total_tokens=384,
        )

        # 记录 Token 用量（Metrics）
        record_token_usage(
            model="gpt-4o",
            prompt_tokens=256,
            completion_tokens=128,
            total_tokens=384,
        )

        # 记录 LLM 延迟（Metrics）
        get_llm_duration().record(300.0, attributes={"model": "gpt-4o"})

        logger.info(
            "LLM 返回结果: prompt_tokens=256, completion_tokens=128, total=384"
        )

        # 模型决定调用工具
        record_routing_decision(model_span, "tools")
        model_span.add_event("tool_start", {"tool.name": "read_file"})

        # 记录工具调用信息（Tracing）
        trace_record_tool_call(model_span, tool_name="read_file", args_summary="path=src/main.py")

    # ─── 子 Span 2: 路由决策 ───
    with span("ohmycode.agent.should_continue") as route_span:
        record_routing_decision(route_span, "tools")
        logger.debug("路由决策: → tools")

    # ─── 子 Span 3: 工具执行 ───
    with span(
        "ohmycode.tools.read_file",
        kind=trace.SpanKind.CLIENT,
        attributes={"tool.name": "read_file", "tool.args_summary": "path=src/main.py"},
    ) as tool_span:
        logger.info("执行工具 read_file(path=src/main.py)")

        # 模拟工具执行
        time.sleep(0.1)

        tool_span.set_attribute("tool.result_size", 2048)
        tool_span.add_event("tool_end", {"tool.name": "read_file", "success": True})

        # 记录工具调用（Metrics）
        record_tool_call(tool_name="read_file", duration_ms=100.0)

        logger.info("工具返回: file_size=2048 bytes")

    # ─── 子 Span 4: 再次调用模型（带工具结果）───
    with span(
        "ohmycode.agent.call_model",
        attributes={"llm.model": "gpt-4o"},
    ) as model_span2:
        logger.info("再次调用 LLM（带工具结果）")
        time.sleep(0.2)

        trace_record_token(
            model_span2,
            model="gpt-4o",
            prompt_tokens=512,
            completion_tokens=256,
            total_tokens=768,
        )
        record_token_usage(
            model="gpt-4o",
            prompt_tokens=512,
            completion_tokens=256,
            total_tokens=768,
        )
        get_llm_duration().record(200.0, attributes={"model": "gpt-4o"})

        # 模型决定结束
        record_routing_decision(model_span2, "__end__")
        logger.info("LLM 生成最终回复: total_tokens=768")

    # ─── 子 Span 5: 模拟一次错误 ───
    with span(
        "ohmycode.tools.write_file",
        kind=trace.SpanKind.CLIENT,
        attributes={"tool.name": "write_file"},
    ) as err_span:
        try:
            logger.warning("尝试写入受保护文件...")
            raise PermissionError("/etc/hosts: 权限被拒绝")
        except PermissionError as e:
            err_span.set_status(trace.StatusCode.ERROR, str(e))
            err_span.record_exception(e)
            record_tool_call(tool_name="write_file", duration_ms=5.0, error="PermissionError")
            record_error(module="tools", error_type="PermissionError")
            logger.error("工具调用失败: %s", e)

    # 记录对话总延迟
    total_duration = (time.time() - start_time) * 1000
    get_conversation_duration().record(total_duration, attributes={"conversation_id": conversation_id})

    logger.info(
        "对话完成 conversation_id=%s duration=%.1fms",
        conversation_id,
        total_duration,
    )


# ─── 3. 等待 Metric 输出并清理 ───

print("\n" + "=" * 70)
print("📊 等待 Metrics 输出（2 秒后自动刷新）...")
print("=" * 70 + "\n")

time.sleep(3)

# 清理
tracer_provider.shutdown()
meter_provider.shutdown()

print("\n" + "=" * 70)
print("✅ 可观测性演示完成！")
print("=" * 70)
print()
print("上方你看到了：")
print("  1. 🔗 Tracing  — 完整的 Span 层级树（conversation → agent → tools）")
print("  2. 📊 Metrics   — Counter（token用量/工具调用/错误）+ Histogram（延迟）")
print("  3. 📝 Logging   — 自动注入 trace_id/span_id 的结构化日志")
print()
print("要启动完整 TUI（带可观测性），在终端运行：")
print("  $ source .venv/bin/activate")
print("  $ python -m ohmycode 2>obs.log &")
print("  $ tail -f obs.log    # 另一个窗口查看追踪数据")
