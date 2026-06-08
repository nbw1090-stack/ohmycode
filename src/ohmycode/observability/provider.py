"""默认可观测性提供者 — 基于 OpenTelemetry ConsoleExporter。

实现 ObservabilityProvider 协议，提供零外部依赖的开箱即用可观测性。
使用 ConsoleSpanExporter 和 ConsoleMetricExporter 输出到 stderr，
兼容 Rich 终端渲染和 Textual TUI。
"""

import logging
import sys
from typing import Any

from opentelemetry import metrics, trace
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import (
    ConsoleMetricExporter,
    PeriodicExportingMetricReader,
)
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import (
    BatchSpanProcessor,
    ConsoleSpanExporter,
    SimpleSpanProcessor,
)

from ohmycode.observability.protocols import ObservabilityProvider as ObservabilityProviderProtocol
from ohmycode.observability.settings import ObservabilitySettings


class DefaultObservabilityProvider:
    """默认可观测性提供者，使用 OTel ConsoleExporter。

    初始化 OTel TracerProvider 和 MeterProvider，
    配置 ConsoleSpanExporter 和 ConsoleMetricExporter 输出到 stderr。

    Args:
        settings: 可观测性配置
    """

    def __init__(self, settings: ObservabilitySettings) -> None:
        self._settings = settings
        self._tracer_provider: TracerProvider | None = None
        self._meter_provider: MeterProvider | None = None
        self._resource: Resource | None = None
        self._initialized = False

    def setup(self) -> None:
        """初始化 OTel 全局资源。

        创建 Resource、TracerProvider、MeterProvider 并设置为全局默认。
        使用 ConsoleExporter 输出到 stderr，不影响 TUI 界面。
        """
        if self._initialized:
            return

        # 创建 OTel Resource（服务标识）
        self._resource = Resource.create(
            {
                "service.name": self._settings.service_name,
                "service.version": "0.1.0",
            }
        )

        # 初始化 TracerProvider
        self._setup_tracer_provider()

        # 初始化 MeterProvider
        self._setup_meter_provider()

        # 配置结构化日志
        self._setup_logging()

        self._initialized = True

    def _setup_tracer_provider(self) -> None:
        """初始化 TracerProvider 并注册为全局默认。"""
        # ConsoleSpanExporter 输出到 stderr，避免干扰 TUI
        console_exporter = ConsoleSpanExporter(out=sys.stderr)

        # 使用 SimpleSpanProcessor 保证同步输出（开发友好）
        # 生产环境可替换为 BatchSpanProcessor
        span_processor = SimpleSpanProcessor(console_exporter)

        self._tracer_provider = TracerProvider(
            resource=self._resource,
        )
        self._tracer_provider.add_span_processor(span_processor)

        # 设置为全局默认
        trace.set_tracer_provider(self._tracer_provider)

    def _setup_meter_provider(self) -> None:
        """初始化 MeterProvider 并注册为全局默认。"""
        # ConsoleMetricExporter 输出到 stderr
        console_exporter = ConsoleMetricExporter(out=sys.stderr)

        # 定期导出指标（每 30 秒）
        metric_reader = PeriodicExportingMetricReader(
            exporter=console_exporter,
            export_interval_millis=30_000,
        )

        self._meter_provider = MeterProvider(
            resource=self._resource,
            metric_readers=[metric_reader],
        )

        # 设置为全局默认
        metrics.set_meter_provider(self._meter_provider)

    def _setup_logging(self) -> None:
        """配置结构化日志。

        配置根日志级别，确保可观测性日志受配置控制。
        """
        log_level = getattr(
            logging, self._settings.log_level.upper(), logging.INFO
        )
        # 配置 ohmycode 日志器
        obs_logger = logging.getLogger("ohmycode")
        obs_logger.setLevel(log_level)

        # 如果没有 handler，添加一个 StreamHandler 到 stderr
        if not obs_logger.handlers:
            handler = logging.StreamHandler(sys.stderr)
            handler.setLevel(log_level)
            formatter = logging.Formatter(
                "%(asctime)s [%(levelname)s] %(name)s "
                "trace_id=%(otelTraceID)s span_id=%(otelSpanID)s "
                "%(message)s",
                datefmt="%Y-%m-%d %H:%M:%S",
            )
            handler.setFormatter(formatter)
            obs_logger.addHandler(handler)

    def shutdown(self) -> None:
        """清理 OTel 资源，刷新未发送的 span 和 metric。"""
        if self._tracer_provider is not None:
            try:
                self._tracer_provider.shutdown()
            except Exception:
                pass  # 静默处理关闭错误

        if self._meter_provider is not None:
            try:
                self._meter_provider.shutdown()
            except Exception:
                pass  # 静默处理关闭错误

        self._initialized = False

    @property
    def tracer_provider(self) -> TracerProvider:
        """返回 OTel TracerProvider 实例。"""
        if self._tracer_provider is None:
            return TracerProvider()
        return self._tracer_provider

    @property
    def meter_provider(self) -> MeterProvider:
        """返回 OTel MeterProvider 实例。"""
        if self._meter_provider is None:
            return MeterProvider()
        return self._meter_provider


class NoOpObservabilityProvider:
    """空操作可观测性提供者。

    当可观测性未启用时使用，所有方法为空操作。
    确保应用在未配置 OTel 时正常运行。
    """

    def setup(self) -> None:
        """空操作。"""

    def shutdown(self) -> None:
        """空操作。"""

    @property
    def tracer_provider(self) -> TracerProvider:
        """返回一个默认的 TracerProvider。"""
        return TracerProvider()

    @property
    def meter_provider(self) -> MeterProvider:
        """返回一个默认的 MeterProvider。"""
        return MeterProvider()
