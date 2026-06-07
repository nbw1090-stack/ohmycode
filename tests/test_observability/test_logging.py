"""测试结构化日志功能。"""

import logging

import pytest

from opentelemetry import trace

from ohmycode.observability.logging import (
    TraceContextFilter,
    get_logger,
    setup_logging,
)
from tests.test_observability.conftest import span_exporter


class TestTraceContextFilter:
    """测试 TraceContextFilter 自动注入 trace_id/span_id。"""

    def test_filter_adds_trace_context(self):
        """应在 LogRecord 上设置 otelTraceID 和 otelSpanID。"""
        f = TraceContextFilter()
        record = logging.LogRecord(
            name="test", level=logging.INFO, pathname="", lineno=0,
            msg="test", args=None, exc_info=None,
        )
        result = f.filter(record)
        assert result is True
        assert hasattr(record, "otelTraceID")
        assert hasattr(record, "otelSpanID")

    def test_filter_adds_valid_trace_id_in_span(self):
        """在活跃 span 内应注入有效的 trace_id。"""
        tracer = trace.get_tracer("test")
        with tracer.start_as_current_span("test-span"):
            f = TraceContextFilter()
            record = logging.LogRecord(
                name="test", level=logging.INFO, pathname="", lineno=0,
                msg="test", args=None, exc_info=None,
            )
            f.filter(record)
            assert record.otelTraceID != "0" * 32

    def test_filter_no_active_span(self):
        """没有活跃 span 时 trace_id 应为全零。"""
        f = TraceContextFilter()
        record = logging.LogRecord(
            name="test", level=logging.INFO, pathname="", lineno=0,
            msg="test", args=None, exc_info=None,
        )
        f.filter(record)
        assert record.otelTraceID == "0" * 32


class TestGetLogger:
    """测试 get_logger() 工厂函数。"""

    def test_returns_logger(self):
        """应返回 Logger 实例。"""
        logger = get_logger("test.module")
        assert isinstance(logger, logging.Logger)

    def test_logger_has_trace_filter(self):
        """Logger 应包含 TraceContextFilter。"""
        logger = get_logger("test.has_filter_unique")
        trace_filters = [f for f in logger.filters if isinstance(f, TraceContextFilter)]
        assert len(trace_filters) >= 1

    def test_logger_caching(self):
        """相同名称应返回相同的 Logger 实例。"""
        logger1 = get_logger("test.cache_unique")
        logger2 = get_logger("test.cache_unique")
        assert logger1 is logger2

    def test_different_names_different_loggers(self):
        """不同名称应返回不同的 Logger 实例。"""
        logger1 = get_logger("test.name_a_unique")
        logger2 = get_logger("test.name_b_unique")
        assert logger1 is not logger2


class TestSetupLogging:
    """测试 setup_logging() 配置函数。"""

    def test_setup_sets_level(self):
        """应设置 ohmycode Logger 的日志级别。"""
        setup_logging(level="DEBUG")
        root_logger = logging.getLogger("ohmycode")
        assert root_logger.level == logging.DEBUG

    def test_setup_adds_handler(self):
        """应为 ohmycode Logger 添加 Handler。"""
        root_logger = logging.getLogger("ohmycode")
        root_logger.handlers.clear()

        setup_logging(level="INFO")
        assert len(root_logger.handlers) >= 1

    def test_setup_idempotent(self):
        """多次调用不应重复添加 Handler。"""
        root_logger = logging.getLogger("ohmycode")
        root_logger.handlers.clear()

        setup_logging(level="INFO")
        count = len(root_logger.handlers)
        setup_logging(level="DEBUG")
        assert len(root_logger.handlers) == count


class TestLoggingWithTracing:
    """测试日志与 Tracing 的集成。"""

    def test_log_in_span_has_trace_id(self):
        """在 span 内记录日志应包含 trace_id。"""
        tracer = trace.get_tracer("test")

        with tracer.start_as_current_span("test-span") as s:
            f = TraceContextFilter()
            record = logging.LogRecord(
                name="test", level=logging.INFO, pathname="", lineno=0,
                msg="test message", args=None, exc_info=None,
            )
            f.filter(record)
            assert record.otelTraceID != "0" * 32
            span_context = s.get_span_context()
            expected = format(span_context.trace_id, "032x")
            assert record.otelTraceID == expected
