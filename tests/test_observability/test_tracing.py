"""测试 Tracing 埋点功能。"""

import pytest

from opentelemetry import trace

from ohmycode.observability.tracing import (
    get_tracer,
    record_routing_decision,
    record_tool_call,
    record_token_usage,
    span,
    trace_conversation,
)
from tests.test_observability.conftest import span_exporter


class TestGetTracer:
    """测试 get_tracer() 函数。"""

    def test_returns_tracer_instance(self):
        """应返回 OTel Tracer 实例。"""
        from opentelemetry.trace import Tracer
        tracer = get_tracer("test")
        assert isinstance(tracer, Tracer)

    def test_default_tracer_name(self):
        """默认 tracer 名称为 ohmycode。"""
        tracer = get_tracer()
        assert tracer is not None


class TestSpanContextManager:
    """测试 span() 上下文管理器。"""

    def test_creates_span(self):
        """应在 TracerProvider 中创建新的 span。"""
        with span("test.span"):
            pass
        spans = span_exporter.get_finished_spans()
        assert len(spans) == 1
        assert spans[0].name == "test.span"

    def test_span_with_attributes(self):
        """应将 attributes 附加到 span。"""
        with span("test.span", attributes={"key": "value"}):
            pass
        spans = span_exporter.get_finished_spans()
        assert spans[0].attributes["key"] == "value"

    def test_span_records_exception(self):
        """异常应被记录到 span。"""
        with pytest.raises(ValueError):
            with span("test.span"):
                raise ValueError("test error")

        spans = span_exporter.get_finished_spans()
        assert len(spans) == 1
        s = spans[0]
        assert s.status.status_code == trace.StatusCode.ERROR
        # 应包含 exception 事件
        events = s.events
        assert any(
            "error" in str(e.name).lower() or "exception" in str(e.name).lower()
            for e in events
        )

    def test_span_status_ok_on_success(self):
        """成功完成时 span 状态应为 UNSET（默认）。"""
        with span("test.span"):
            pass
        spans = span_exporter.get_finished_spans()
        assert spans[0].status.status_code == trace.StatusCode.UNSET


class TestTraceConversation:
    """测试 trace_conversation() 函数。"""

    def test_creates_conversation_span(self):
        """应创建对话级别的 span。"""
        conv_span = trace_conversation("test-123")
        assert conv_span is not None
        assert conv_span.name == "ohmycode.conversation"
        conv_span.end()

    def test_conversation_span_has_id_attribute(self):
        """对话 span 应包含 conversation.id 属性。"""
        conv_span = trace_conversation("test-456")
        attrs = dict(conv_span.attributes) if conv_span.attributes else {}
        assert "conversation.id" in attrs
        assert attrs["conversation.id"] == "test-456"
        conv_span.end()


class TestRecordTokenUsage:
    """测试 record_token_usage() 函数。"""

    def test_sets_token_attributes(self):
        """应在 span 上设置 token 用量属性。"""
        with span("test.llm") as s:
            record_token_usage(
                s,
                model="gpt-4o",
                prompt_tokens=100,
                completion_tokens=50,
                total_tokens=150,
            )

        spans = span_exporter.get_finished_spans()
        attrs = spans[0].attributes
        assert attrs["llm.model"] == "gpt-4o"
        assert attrs["llm.prompt_tokens"] == 100
        assert attrs["llm.completion_tokens"] == 50
        assert attrs["llm.total_tokens"] == 150


class TestRecordRoutingDecision:
    """测试 record_routing_decision() 函数。"""

    def test_adds_routing_event(self):
        """应在 span 上添加路由决策事件。"""
        with span("test.routing") as s:
            record_routing_decision(s, "tools")

        spans = span_exporter.get_finished_spans()
        events = spans[0].events
        assert len(events) == 1
        assert events[0].name == "routing_decision"
        assert events[0].attributes["decision"] == "tools"


class TestRecordToolCall:
    """测试 record_tool_call() 函数。"""

    def test_sets_tool_attributes(self):
        """应在 span 上设置工具调用属性。"""
        with span("test.tool") as s:
            record_tool_call(s, tool_name="read_file", args_summary="path=/tmp/test")

        spans = span_exporter.get_finished_spans()
        attrs = spans[0].attributes
        assert attrs["tool.name"] == "read_file"
        assert attrs["tool.args_summary"] == "path=/tmp/test"

    def test_no_args_summary(self):
        """args_summary 为空时不应设置 tool.args_summary 属性。"""
        with span("test.tool") as s:
            record_tool_call(s, tool_name="echo")

        spans = span_exporter.get_finished_spans()
        attrs = spans[0].attributes
        assert attrs["tool.name"] == "echo"
        assert "tool.args_summary" not in attrs
