"""可观测性提供者协议定义。

定义 ObservabilityProvider Protocol，与 LLMProvider、ToolProvider、ContextProvider
同级，由 Assembler 组合根统一装配。
"""

from typing import Protocol, runtime_checkable

from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.trace import TracerProvider


@runtime_checkable
class ObservabilityProvider(Protocol):
    """可观测性提供者协议。

    任何模块都可以实现此协议来提供不同的可观测性后端。
    默认使用 ConsoleExporter 输出到终端，无需外部服务。

    Methods:
        setup: 初始化可观测性资源（TracerProvider、MeterProvider、Logger）
        shutdown: 清理可观测性资源，刷新未发送的数据
        tracer_provider: 返回 OTel TracerProvider 实例
        meter_provider: 返回 OTel MeterProvider 实例
    """

    def setup(self) -> None:
        """初始化可观测性资源。

        应在应用启动时调用，设置全局 TracerProvider、MeterProvider 和 Logger。
        """
        ...

    def shutdown(self) -> None:
        """清理可观测性资源，刷新未发送的 span 和 metric。

        应在应用关闭时调用。
        """
        ...

    @property
    def tracer_provider(self) -> TracerProvider:
        """返回 OTel TracerProvider 实例。"""
        ...

    @property
    def meter_provider(self) -> MeterProvider:
        """返回 OTel MeterProvider 实例。"""
        ...
