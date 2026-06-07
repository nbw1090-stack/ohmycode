"""可观测性配置。

定义 ObservabilitySettings dataclass，从 TOML 文件和环境变量加载配置。
"""

import os
from dataclasses import dataclass, field


@dataclass
class ObservabilitySettings:
    """可观测性相关配置。

    支持两种配置来源（优先级从高到低）：
        1. 环境变量（OHMYCODE_OBS_* 前缀）
        2. TOML 配置文件 [observability] 段落

    Attributes:
        enabled: 是否启用可观测性
        exporter_type: 导出器类型，支持 "console"（默认）和 "otlp"
        log_level: 日志级别（DEBUG/INFO/WARNING/ERROR）
        service_name: 服务名称，用于 OTel Resource 标识
    """

    enabled: bool = False
    exporter_type: str = "console"
    log_level: str = "INFO"
    service_name: str = "ohmycode"

    @classmethod
    def from_dict(cls, data: dict) -> "ObservabilitySettings":
        """从字典创建配置，环境变量优先级更高。

        Args:
            data: TOML 中 [observability] 段落的字典

        Returns:
            ObservabilitySettings 实例
        """
        # 环境变量覆盖
        env_enabled = os.environ.get("OHMYCODE_OBS_ENABLED")
        env_exporter = os.environ.get("OHMYCODE_OBS_EXPORTER_TYPE")
        env_log_level = os.environ.get("OHMYCODE_OBS_LOG_LEVEL")
        env_service_name = os.environ.get("OHMYCODE_OBS_SERVICE_NAME")

        # 解析 enabled：环境变量优先，否则使用 TOML 值
        if env_enabled is not None:
            enabled = env_enabled.lower() in ("true", "1", "yes")
        else:
            enabled = bool(data.get("enabled", False))

        return cls(
            enabled=enabled,
            exporter_type=env_exporter or data.get("exporter_type", "console"),
            log_level=env_log_level or data.get("log_level", "INFO"),
            service_name=env_service_name or data.get("service_name", "ohmycode"),
        )
