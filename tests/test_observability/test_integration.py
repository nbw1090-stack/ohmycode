"""集成测试 — 验证 Agent 完整流程的 trace 链路和指标记录。"""

import pytest

from opentelemetry import trace

from ohmycode.observability.metrics import (
    get_conversation_duration,
    record_error,
    record_token_usage,
    record_tool_call,
)
from ohmycode.observability.tracing import (
    get_tracer,
    record_routing_decision,
    record_token_usage as record_token_span,
    record_tool_call as record_tool_span,
)
from ohmycode.observability.spans import (
    SPAN_AGENT_CALL_MODEL,
    TRACE_CONVERSATION,
)
from tests.test_observability.conftest import span_exporter, metric_reader


class TestFullConversationTrace:
    """测试完整对话流程的 Trace 链路。"""

    def test_conversation_trace_structure(self):
        """一次对话应产生 conversation -> agent 的 span 层级。"""
        tracer = get_tracer()

        with tracer.start_as_current_span(TRACE_CONVERSATION) as conv_span:
            conv_span.set_attribute("conversation.id", "test-001")

            with tracer.start_as_current_span(SPAN_AGENT_CALL_MODEL) as agent_span:
                agent_span.set_attribute("has_tool_calls", False)

        spans = span_exporter.get_finished_spans()
        assert len(spans) == 2

        agent_span = [s for s in spans if s.name == SPAN_AGENT_CALL_MODEL][0]
        conv_span_result = [s for s in spans if s.name == TRACE_CONVERSATION][0]

        assert agent_span.parent is not None
        assert agent_span.parent.span_id == conv_span_result.context.span_id

    def test_conversation_with_tool_call(self):
        """包含工具调用的对话应产生完整 span 链。"""
        tracer = get_tracer()

        with tracer.start_as_current_span(TRACE_CONVERSATION) as conv:
            conv.set_attribute("conversation.id", "test-002")

            with tracer.start_as_current_span(SPAN_AGENT_CALL_MODEL) as agent1:
                agent1.set_attribute("has_tool_calls", True)
                agent1.set_attribute("tool_names", "read_file")
                record_routing_decision(agent1, "tools")

            with tracer.start_as_current_span("ohmycode.tools.read_file") as tool_span:
                record_tool_span(tool_span, tool_name="read_file", args_summary="path=/tmp/test")
                tool_span.set_attribute("result_size", 1024)

            with tracer.start_as_current_span(SPAN_AGENT_CALL_MODEL) as agent2:
                agent2.set_attribute("has_tool_calls", False)
                record_routing_decision(agent2, "__end__")

        spans = span_exporter.get_finished_spans()
        assert len(spans) == 4

        conv_span = [s for s in spans if s.name == TRACE_CONVERSATION][0]
        assert conv_span.parent is None

        child_spans = [s for s in spans if s.name != TRACE_CONVERSATION]
        for child in child_spans:
            if child.parent is not None:
                assert child.parent.span_id == conv_span.context.span_id

    def test_conversation_with_error(self):
        """对话中发生错误应记录到 span。"""
        tracer = get_tracer()

        with tracer.start_as_current_span(TRACE_CONVERSATION) as conv:
            conv.set_attribute("conversation.id", "test-003")
            try:
                with tracer.start_as_current_span(SPAN_AGENT_CALL_MODEL) as agent:
                    raise ValueError("模拟 LLM 错误")
            except ValueError:
                pass

        spans = span_exporter.get_finished_spans()
        agent_span = [s for s in spans if s.name == SPAN_AGENT_CALL_MODEL][0]
        assert agent_span.status.status_code == trace.StatusCode.ERROR


class TestFullConversationMetrics:
    """测试完整对话流程的 Metrics 收集。"""

    def test_token_and_tool_metrics(self):
        """完整对话应记录 token 和工具指标。"""
        record_token_usage(
            model="gpt-4o",
            prompt_tokens=200,
            completion_tokens=100,
            total_tokens=300,
        )
        record_tool_call(tool_name="read_file", duration_ms=50.0)
        record_tool_call(tool_name="write_file", duration_ms=120.0, error="PermissionError")
        get_conversation_duration().record(2500.0, attributes={"model": "gpt-4o"})
        record_error(module="tools", error_type="PermissionError")

        metrics_data = metric_reader.get_metrics_data()
        assert metrics_data is not None
        assert len(metrics_data.resource_metrics) > 0

    def test_multiple_conversations_accumulate(self):
        """多次对话应累加 token 计数。"""
        record_token_usage(model="gpt-4o", prompt_tokens=100, completion_tokens=50, total_tokens=150)
        get_conversation_duration().record(1000.0, attributes={"model": "gpt-4o"})

        record_token_usage(model="gpt-4o", prompt_tokens=150, completion_tokens=75, total_tokens=225)
        get_conversation_duration().record(1500.0, attributes={"model": "gpt-4o"})

        metrics_data = metric_reader.get_metrics_data()
        assert metrics_data is not None
        assert len(metrics_data.resource_metrics) > 0


class TestTraceAndMetricsIntegration:
    """测试 Tracing 和 Metrics 的联合使用。"""

    def test_llm_call_with_tracing_and_metrics(self):
        """LLM 调用应同时记录 span 和 metric。"""
        tracer = get_tracer()

        with tracer.start_as_current_span("ohmycode.llm.invoke") as llm_span:
            record_token_span(
                llm_span,
                model="gpt-4o",
                prompt_tokens=100,
                completion_tokens=50,
                total_tokens=150,
            )
            record_token_usage(
                model="gpt-4o",
                prompt_tokens=100,
                completion_tokens=50,
                total_tokens=150,
            )

        spans = span_exporter.get_finished_spans()
        assert len(spans) == 1
        assert spans[0].attributes["llm.model"] == "gpt-4o"
        assert spans[0].attributes["llm.total_tokens"] == 150

        metrics_data = metric_reader.get_metrics_data()
        assert metrics_data is not None
        assert len(metrics_data.resource_metrics) > 0

    def test_tool_call_with_tracing_and_metrics(self):
        """工具调用应同时记录 span 和 metric。"""
        tracer = get_tracer()

        with tracer.start_as_current_span("ohmycode.tools.read_file") as tool_span:
            record_tool_span(tool_span, tool_name="read_file", args_summary="path=/tmp/test")
            record_tool_call(tool_name="read_file", duration_ms=42.0)

        spans = span_exporter.get_finished_spans()
        assert len(spans) == 1
        assert spans[0].attributes["tool.name"] == "read_file"

        metrics_data = metric_reader.get_metrics_data()
        assert metrics_data is not None
        assert len(metrics_data.resource_metrics) > 0
