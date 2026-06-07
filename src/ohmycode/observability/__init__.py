"""可观测性模块 — 基于 OpenTelemetry 的 Tracing、Logging、Metrics 三大支柱。

提供统一的可观测性接口，遵循项目的 Assembly Pattern：
- ObservabilityProvider Protocol 定义接口
- DefaultObservabilityProvider 使用 ConsoleExporter（零外部依赖）
- 全局便捷函数：get_tracer()、get_meter()、get_logger()

用法::

    from ohmycode.observability import get_tracer, get_meter, get_logger

    tracer = get_tracer()
    meter = get_meter()
    logger = get_logger(__name__)

公共接口：
    get_tracer   — 获取 OTel Tracer
    get_meter    — 获取 OTel Meter
    get_logger   — 获取自动注入 trace_id/span_id 的 Logger
    setup_observability — 初始化可观测性（由 Assembler 调用）
    shutdown_observability — 清理可观测性资源
"""

from ohmycode.observability.logging import get_logger, setup_logging
from ohmycode.observability.metrics import get_meter
from ohmycode.observability.tracing import get_tracer

# 模块级 Provider 实例，由 setup_observability 设置
_provider = None


def setup_observability(settings: "ObservabilitySettings") -> None:
    """初始化可观测性系统。

    由 Assembler 组合根在应用启动时调用。
    根据 settings.enabled 决定是否实际初始化 OTel 资源。

    Args:
        settings: 可观测性配置
    """
    global _provider

    if not settings.enabled:
        return

    from ohmycode.observability.provider import DefaultObservabilityProvider

    _provider = DefaultObservabilityProvider(settings)
    _provider.setup()

    # 初始化日志系统
    setup_logging(level=settings.log_level)


def shutdown_observability() -> None:
    """清理可观测性资源。

    由应用关闭时调用，刷新未发送的 span 和 metric。
    """
    global _provider
    if _provider is not None:
        _provider.shutdown()
        _provider = None


def get_provider():
    """获取当前可观测性 Provider 实例。

    Returns:
        DefaultObservabilityProvider 实例，或 None（未启用时）
    """
    return _provider


__all__ = [
    "get_tracer",
    "get_meter",
    "get_logger",
    "setup_observability",
    "shutdown_observability",
    "get_provider",
]
