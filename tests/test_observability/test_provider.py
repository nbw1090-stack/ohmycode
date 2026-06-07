"""测试 DefaultObservabilityProvider 和 NoOpObservabilityProvider。"""

import pytest

from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.trace import TracerProvider

from ohmycode.observability.provider import (
    DefaultObservabilityProvider,
    NoOpObservabilityProvider,
)
from ohmycode.observability.settings import ObservabilitySettings


class TestDefaultObservabilityProvider:
    """测试 DefaultObservabilityProvider 初始化和方法。"""

    def test_init_stores_settings(self):
        """构造函数应存储 settings。"""
        settings = ObservabilitySettings(enabled=True)
        provider = DefaultObservabilityProvider(settings)
        assert provider._settings is settings

    def test_setup_initializes_tracer_provider(self):
        """setup() 应初始化 TracerProvider。"""
        settings = ObservabilitySettings(enabled=True)
        provider = DefaultObservabilityProvider(settings)
        provider.setup()
        assert provider._tracer_provider is not None
        assert isinstance(provider.tracer_provider, TracerProvider)
        provider.shutdown()

    def test_setup_initializes_meter_provider(self):
        """setup() 应初始化 MeterProvider。"""
        settings = ObservabilitySettings(enabled=True)
        provider = DefaultObservabilityProvider(settings)
        provider.setup()
        assert provider._meter_provider is not None
        assert isinstance(provider.meter_provider, MeterProvider)
        provider.shutdown()

    def test_setup_idempotent(self):
        """多次调用 setup() 应为幂等。"""
        settings = ObservabilitySettings(enabled=True)
        provider = DefaultObservabilityProvider(settings)
        provider.setup()
        first_tp = provider._tracer_provider
        provider.setup()  # 不应重新创建
        assert provider._tracer_provider is first_tp
        provider.shutdown()

    def test_tracer_provider_returns_default_before_setup(self):
        """setup() 前访问 tracer_provider 应返回默认 TracerProvider。"""
        settings = ObservabilitySettings(enabled=True)
        provider = DefaultObservabilityProvider(settings)
        tp = provider.tracer_provider
        assert isinstance(tp, TracerProvider)

    def test_meter_provider_returns_default_before_setup(self):
        """setup() 前访问 meter_provider 应返回默认 MeterProvider。"""
        settings = ObservabilitySettings(enabled=True)
        provider = DefaultObservabilityProvider(settings)
        mp = provider.meter_provider
        assert isinstance(mp, MeterProvider)

    def test_shutdown_clears_initialized(self):
        """shutdown() 应重置初始化状态。"""
        settings = ObservabilitySettings(enabled=True)
        provider = DefaultObservabilityProvider(settings)
        provider.setup()
        assert provider._initialized is True
        provider.shutdown()
        assert provider._initialized is False

    def test_shutdown_without_setup_is_safe(self):
        """未 setup 时调用 shutdown() 不应报错。"""
        settings = ObservabilitySettings(enabled=True)
        provider = DefaultObservabilityProvider(settings)
        provider.shutdown()  # 不应抛出异常

    def test_setup_creates_resource(self):
        """setup() 应创建包含 service.name 的 Resource。"""
        settings = ObservabilitySettings(enabled=True, service_name="test-svc")
        provider = DefaultObservabilityProvider(settings)
        provider.setup()
        assert provider._resource is not None
        provider.shutdown()


class TestNoOpObservabilityProvider:
    """测试 NoOpObservabilityProvider 空操作行为。"""

    def test_setup_is_noop(self):
        """setup() 应为空操作。"""
        provider = NoOpObservabilityProvider()
        provider.setup()  # 不应抛出异常

    def test_shutdown_is_noop(self):
        """shutdown() 应为空操作。"""
        provider = NoOpObservabilityProvider()
        provider.shutdown()  # 不应抛出异常

    def test_tracer_provider_returns_default(self):
        """tracer_provider 应返回默认 TracerProvider。"""
        provider = NoOpObservabilityProvider()
        tp = provider.tracer_provider
        assert isinstance(tp, TracerProvider)

    def test_meter_provider_returns_default(self):
        """meter_provider 应返回默认 MeterProvider。"""
        provider = NoOpObservabilityProvider()
        mp = provider.meter_provider
        assert isinstance(mp, MeterProvider)


class TestProviderIntegration:
    """测试 Provider 集成流程。"""

    def test_full_lifecycle(self):
        """完整生命周期：setup -> 使用 -> shutdown。"""
        settings = ObservabilitySettings(
            enabled=True,
            log_level="DEBUG",
            service_name="test-lifecycle",
        )
        provider = DefaultObservabilityProvider(settings)

        # setup
        provider.setup()

        # 使用 tracer
        tracer = provider.tracer_provider.get_tracer("test")
        with tracer.start_as_current_span("test-span") as s:
            s.set_attribute("test.key", "test.value")

        # 使用 meter
        meter = provider.meter_provider.get_meter("test")
        counter = meter.create_counter("test.counter")
        counter.add(1, attributes={"test": "value"})

        # shutdown
        provider.shutdown()
        assert provider._initialized is False
