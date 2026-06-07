"""测试 ObservabilityProvider Protocol 接口。"""

import pytest

from ohmycode.observability.protocols import ObservabilityProvider


class TestObservabilityProviderProtocol:
    """验证 Protocol 接口定义和 runtime_checkable 行为。"""

    def test_protocol_is_runtime_checkable(self):
        """Protocol 应使用 @runtime_checkable 装饰器。"""
        assert hasattr(ObservabilityProvider, "__protocol_attrs__") or hasattr(
            ObservabilityProvider, "__abstractmethods__"
        )

    def test_conforming_class_passes_isinstance(self):
        """实现所有方法的类应通过 isinstance 检查。"""

        class ConformingProvider:
            def setup(self) -> None:
                pass

            def shutdown(self) -> None:
                pass

            @property
            def tracer_provider(self):
                from opentelemetry.sdk.trace import TracerProvider
                return TracerProvider()

            @property
            def meter_provider(self):
                from opentelemetry.sdk.metrics import MeterProvider
                return MeterProvider()

        provider = ConformingProvider()
        assert isinstance(provider, ObservabilityProvider)

    def test_non_conforming_class_fails_isinstance(self):
        """未实现必要方法的类不应通过 isinstance 检查。"""

        class NonConforming:
            pass

        provider = NonConforming()
        assert not isinstance(provider, ObservabilityProvider)

    def test_partial_conforming_fails_isinstance(self):
        """只实现部分方法的类不应通过 isinstance 检查。"""

        class PartialProvider:
            def setup(self) -> None:
                pass

        provider = PartialProvider()
        assert not isinstance(provider, ObservabilityProvider)

    def test_default_observability_provider_conforms(self):
        """DefaultObservabilityProvider 应通过 isinstance 检查。"""
        from ohmycode.observability.provider import DefaultObservabilityProvider
        from ohmycode.observability.settings import ObservabilitySettings

        settings = ObservabilitySettings(enabled=True)
        provider = DefaultObservabilityProvider(settings)
        assert isinstance(provider, ObservabilityProvider)

    def test_noop_provider_conforms(self):
        """NoOpObservabilityProvider 应通过 isinstance 检查。"""
        from ohmycode.observability.provider import NoOpObservabilityProvider

        provider = NoOpObservabilityProvider()
        assert isinstance(provider, ObservabilityProvider)
