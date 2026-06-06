"""配置加载测试。"""

import os
import tempfile
from pathlib import Path
from unittest.mock import patch

from ohmycode.config.settings import Settings


class TestLLMSettings:
    """LLM 配置从环境变量读取的测试。"""

    def test_default_model(self):
        """默认模型应为 gpt-4o-mini。"""
        settings = Settings()
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("OPENAI_MODEL", None)
            assert settings.llm.model == "gpt-4o-mini"

    def test_custom_model_from_env(self):
        """从环境变量读取自定义模型名。"""
        settings = Settings()
        with patch.dict(os.environ, {"OPENAI_MODEL": "gpt-4o"}):
            assert settings.llm.model == "gpt-4o"

    def test_temperature_from_env(self):
        """从环境变量读取温度参数。"""
        settings = Settings()
        with patch.dict(os.environ, {"OPENAI_TEMPERATURE": "0.7"}):
            assert settings.llm.temperature == 0.7

    def test_api_key_from_env(self):
        """从环境变量读取 API Key。"""
        settings = Settings()
        with patch.dict(os.environ, {"OPENAI_API_KEY": "sk-test"}):
            assert settings.llm.api_key == "sk-test"

    def test_api_key_missing(self):
        """API Key 未设置时应返回空字符串。"""
        settings = Settings()
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("OPENAI_API_KEY", None)
            assert settings.llm.api_key == ""

    def test_base_url_from_env(self):
        """从环境变量读取自定义 API 地址。"""
        settings = Settings()
        with patch.dict(os.environ, {"OPENAI_BASE_URL": "https://custom.api.com/v1"}):
            assert settings.llm.base_url == "https://custom.api.com/v1"

    def test_base_url_default_empty(self):
        """BASE_URL 默认为空。"""
        settings = Settings()
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("OPENAI_BASE_URL", None)
            assert settings.llm.base_url == ""


class TestSettings:
    """Settings 配置测试。"""

    def test_default_settings(self):
        """默认配置应包含正确的非 LLM 默认值。"""
        settings = Settings()
        assert settings.agent.recursion_limit == 25
        assert settings.tools.enabled == []  # 空列表表示启用全部工具

    def test_from_toml_nonexistent_file(self):
        """加载不存在的文件应返回默认配置。"""
        settings = Settings.from_toml(Path("/nonexistent/config.toml"))
        assert settings.agent.recursion_limit == 25

    def test_from_toml_custom_agent_values(self):
        """从自定义 TOML 内容加载 Agent 配置。"""
        with tempfile.NamedTemporaryFile(mode="wb", suffix=".toml", delete=False) as f:
            f.write(b"[agent]\nrecursion_limit = 50\n")
            f.flush()
            settings = Settings.from_toml(Path(f.name))
            assert settings.agent.recursion_limit == 50
