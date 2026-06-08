"""应用配置，使用 dataclass 定义。

LLM 相关配置从环境变量（.env 文件）读取，非 LLM 配置从 TOML 文件加载。
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ohmycode.observability.settings import ObservabilitySettings

try:
    import tomllib
except ModuleNotFoundError:
    import tomli as tomllib  # type: ignore[no-redef]


@dataclass
class LLMSettings:
    """LLM 相关配置，全部从环境变量读取。

    环境变量：
        OPENAI_API_KEY      — API Key（必填）
        OPENAI_MODEL        — 模型名称（默认 gpt-4o-mini）
        OPENAI_TEMPERATURE  — 温度参数（默认 0.0）
        OPENAI_BASE_URL     — 自定义 API 地址（可选，留空使用官方地址）
    """

    @property
    def api_key(self) -> str:
        return os.environ.get("OPENAI_API_KEY", "")

    @property
    def model(self) -> str:
        return os.environ.get("OPENAI_MODEL", "gpt-4o-mini")

    @property
    def temperature(self) -> float:
        return float(os.environ.get("OPENAI_TEMPERATURE", "0.0"))

    @property
    def base_url(self) -> str:
        return os.environ.get("OPENAI_BASE_URL", "")


@dataclass
class AgentSettings:
    """Agent 相关配置。"""
    recursion_limit: int = 25


@dataclass
class ToolSettings:
    """工具相关配置。"""
    enabled: list[str] = field(default_factory=list)  # 空=全部启用，否则只启用列表中的工具


@dataclass
class Settings:
    """应用全局配置。

    LLM 配置始终从环境变量读取。
    Agent、工具和可观测性配置从 TOML 文件加载，缺失字段使用默认值。
    """

    llm: LLMSettings = field(default_factory=LLMSettings)
    agent: AgentSettings = field(default_factory=AgentSettings)
    tools: ToolSettings = field(default_factory=ToolSettings)
    observability: ObservabilitySettings | None = field(default=None)

    @classmethod
    def from_toml(cls, path: Path) -> "Settings":
        """从 TOML 文件加载非 LLM 配置，缺失的字段使用默认值。

        LLM 配置不在此加载，始终从环境变量读取。
        可观测性配置支持环境变量覆盖 TOML 值。
        """
        if not path.exists():
            return cls()

        with open(path, "rb") as f:
            data = tomllib.load(f)

        agent_data = data.get("agent", {})
        tool_data = data.get("tools", {})
        obs_data = data.get("observability", {})

        # 延迟导入避免循环依赖
        from ohmycode.observability.settings import ObservabilitySettings

        return cls(
            agent=AgentSettings(**agent_data),
            tools=ToolSettings(**tool_data),
            observability=ObservabilitySettings.from_dict(obs_data),
        )
