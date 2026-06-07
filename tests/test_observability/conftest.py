"""测试可观测性模块共享的 OTel Provider 设置。

OTel 全局 TracerProvider 和 MeterProvider 只能设置一次，
因此所有测试文件必须共享同一组 Provider 和 Exporter/Reader。
"""

import pytest

from opentelemetry import metrics, trace
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import InMemoryMetricReader
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import (
    InMemorySpanExporter,
)

from ohmycode.observability.metrics import reset_metrics

# ===== 全局 InMemory Exporter/Reader =====

span_exporter = InMemorySpanExporter()
metric_reader = InMemoryMetricReader()

# ===== 初始化全局 Provider（仅一次）=====
_tracer_provider = TracerProvider()
_tracer_provider.add_span_processor(SimpleSpanProcessor(span_exporter))
trace.set_tracer_provider(_tracer_provider)

_meter_provider = MeterProvider(metric_readers=[metric_reader])
metrics.set_meter_provider(_meter_provider)


@pytest.fixture(autouse=True)
def _reset_otel_state():
    """每个测试前重置 OTel 状态：清除 span 和重置 metrics 缓存。"""
    span_exporter.clear()
    reset_metrics()
    yield
    span_exporter.clear()
    reset_metrics()
