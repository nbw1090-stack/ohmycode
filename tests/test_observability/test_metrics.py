"""测试 Metrics 收集功能。"""

import pytest

from opentelemetry import metrics
from opentelemetry.metrics import Counter, Histogram, Meter

from ohmycode.observability.metrics import (
    get_conversation_duration,
    get_error_counter,
    get_llm_duration,
    get_meter,
    get_tool_call_counter,
    get_tool_duration,
    get_tool_error_counter,
    get_token_counter,
    record_error,
    record_token_usage,
    record_tool_call,
    reset_metrics,
)
from tests.test_observability.conftest import metric_reader


class TestGetMeter:
    """测试 get_meter() 函数。"""

    def test_returns_meter_instance(self):
        """应返回 OTel Meter 实例。"""
        meter = get_meter()
        assert isinstance(meter, Meter)


class TestTokenCounter:
    """测试 Token 用量计数器。"""

    def test_get_token_counter(self):
        """应返回 Counter 实例。"""
        counter = get_token_counter()
        assert isinstance(counter, Counter)

    def test_record_token_usage(self):
        """record_token_usage 应递增 token 计数。"""
        record_token_usage(
            model="gpt-4o",
            prompt_tokens=100,
            completion_tokens=50,
            total_tokens=150,
        )

        metrics_data = metric_reader.get_metrics_data()
        assert metrics_data is not None
        resource_metrics = metrics_data.resource_metrics
        assert len(resource_metrics) > 0

    def test_record_token_usage_multiple(self):
        """多次记录应累加。"""
        record_token_usage(
            model="gpt-4o",
            prompt_tokens=100,
            completion_tokens=50,
            total_tokens=150,
        )
        record_token_usage(
            model="gpt-4o",
            prompt_tokens=200,
            completion_tokens=100,
            total_tokens=300,
        )

        metrics_data = metric_reader.get_metrics_data()
        assert metrics_data is not None
        resource_metrics = metrics_data.resource_metrics
        assert len(resource_metrics) > 0


class TestToolMetrics:
    """测试工具调用 Metrics。"""

    def test_get_tool_call_counter(self):
        """应返回 Counter 实例。"""
        counter = get_tool_call_counter()
        assert isinstance(counter, Counter)

    def test_get_tool_duration(self):
        """应返回 Histogram 实例。"""
        hist = get_tool_duration()
        assert isinstance(hist, Histogram)

    def test_get_tool_error_counter(self):
        """应返回 Counter 实例。"""
        counter = get_tool_error_counter()
        assert isinstance(counter, Counter)

    def test_record_tool_call_success(self):
        """成功工具调用应记录调用计数和延迟。"""
        record_tool_call(tool_name="read_file", duration_ms=42.5)

        metrics_data = metric_reader.get_metrics_data()
        assert metrics_data is not None
        resource_metrics = metrics_data.resource_metrics
        assert len(resource_metrics) > 0

    def test_record_tool_call_with_error(self):
        """失败工具调用应额外记录错误计数。"""
        record_tool_call(tool_name="write_file", duration_ms=10.0, error="PermissionError")

        metrics_data = metric_reader.get_metrics_data()
        assert metrics_data is not None
        resource_metrics = metrics_data.resource_metrics
        assert len(resource_metrics) > 0


class TestConversationMetrics:
    """测试对话级别 Metrics。"""

    def test_get_conversation_duration(self):
        """应返回 Histogram 实例。"""
        hist = get_conversation_duration()
        assert isinstance(hist, Histogram)

    def test_record_conversation_duration(self):
        """应记录对话延迟。"""
        get_conversation_duration().record(1234.5, attributes={"model": "gpt-4o"})

        metrics_data = metric_reader.get_metrics_data()
        assert metrics_data is not None
        resource_metrics = metrics_data.resource_metrics
        assert len(resource_metrics) > 0


class TestErrorMetrics:
    """测试错误 Metrics。"""

    def test_get_error_counter(self):
        """应返回 Counter 实例。"""
        counter = get_error_counter()
        assert isinstance(counter, Counter)

    def test_record_error(self):
        """应记录错误指标。"""
        record_error(module="agent", error_type="ValueError")

        metrics_data = metric_reader.get_metrics_data()
        assert metrics_data is not None
        resource_metrics = metrics_data.resource_metrics
        assert len(resource_metrics) > 0


class TestResetMetrics:
    """测试 reset_metrics() 函数。"""

    def test_reset_clears_caches(self):
        """reset_metrics 应清除所有缓存的指标实例。"""
        get_token_counter()
        reset_metrics()
        counter = get_token_counter()
        assert counter is not None


class TestLLMDuration:
    """测试 LLM 调用延迟 Histogram。"""

    def test_get_llm_duration(self):
        """应返回 Histogram 实例。"""
        hist = get_llm_duration()
        assert isinstance(hist, Histogram)

    def test_record_llm_duration(self):
        """应记录 LLM 调用延迟。"""
        get_llm_duration().record(500.0, attributes={"model": "gpt-4o"})

        metrics_data = metric_reader.get_metrics_data()
        assert metrics_data is not None
        resource_metrics = metrics_data.resource_metrics
        assert len(resource_metrics) > 0
