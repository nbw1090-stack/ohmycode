"""测试 ObservabilitySettings 配置解析。"""

import os

import pytest

from ohmycode.observability.settings import ObservabilitySettings


class TestObservabilitySettings:
    """测试 ObservabilitySettings dataclass 和 from_dict 方法。"""

    def test_default_values(self):
        """默认配置应为 enabled=False, console exporter, INFO level。"""
        settings = ObservabilitySettings()
        assert settings.enabled is False
        assert settings.exporter_type == "console"
        assert settings.log_level == "INFO"
        assert settings.service_name == "ohmycode"

    def test_from_dict_with_empty_data(self):
        """空字典应返回默认值。"""
        settings = ObservabilitySettings.from_dict({})
        assert settings.enabled is False
        assert settings.exporter_type == "console"
        assert settings.log_level == "INFO"

    def test_from_dict_with_values(self):
        """字典值应正确映射到 dataclass 字段。"""
        data = {
            "enabled": True,
            "exporter_type": "otlp",
            "log_level": "DEBUG",
            "service_name": "test-service",
        }
        settings = ObservabilitySettings.from_dict(data)
        assert settings.enabled is True
        assert settings.exporter_type == "otlp"
        assert settings.log_level == "DEBUG"
        assert settings.service_name == "test-service"

    def test_from_dict_partial_values(self):
        """部分字段使用字典值，其余使用默认值。"""
        data = {"enabled": True}
        settings = ObservabilitySettings.from_dict(data)
        assert settings.enabled is True
        assert settings.exporter_type == "console"
        assert settings.log_level == "INFO"

    def test_env_override_enabled(self, monkeypatch):
        """环境变量 OHMYCODE_OBS_ENABLED 应覆盖 TOML 值。"""
        monkeypatch.setenv("OHMYCODE_OBS_ENABLED", "true")
        data = {"enabled": False}
        settings = ObservabilitySettings.from_dict(data)
        assert settings.enabled is True

    def test_env_override_exporter_type(self, monkeypatch):
        """环境变量 OHMYCODE_OBS_EXPORTER_TYPE 应覆盖 TOML 值。"""
        monkeypatch.setenv("OHMYCODE_OBS_EXPORTER_TYPE", "otlp")
        data = {"exporter_type": "console"}
        settings = ObservabilitySettings.from_dict(data)
        assert settings.exporter_type == "otlp"

    def test_env_override_log_level(self, monkeypatch):
        """环境变量 OHMYCODE_OBS_LOG_LEVEL 应覆盖 TOML 值。"""
        monkeypatch.setenv("OHMYCODE_OBS_LOG_LEVEL", "DEBUG")
        data = {"log_level": "INFO"}
        settings = ObservabilitySettings.from_dict(data)
        assert settings.log_level == "DEBUG"

    def test_env_override_service_name(self, monkeypatch):
        """环境变量 OHMYCODE_OBS_SERVICE_NAME 应覆盖 TOML 值。"""
        monkeypatch.setenv("OHMYCODE_OBS_SERVICE_NAME", "custom-service")
        data = {"service_name": "ohmycode"}
        settings = ObservabilitySettings.from_dict(data)
        assert settings.service_name == "custom-service"

    def test_env_enabled_false_values(self, monkeypatch):
        """OHMYCODE_OBS_ENABLED 设为 'false'/'0'/'no' 应视为 False。"""
        for value in ("false", "0", "no"):
            monkeypatch.setenv("OHMYCODE_OBS_ENABLED", value)
            settings = ObservabilitySettings.from_dict({"enabled": True})
            assert settings.enabled is False

    def test_toml_value_used_when_no_env(self, monkeypatch):
        """没有环境变量时使用 TOML 值。"""
        # 确保环境变量不存在
        monkeypatch.delenv("OHMYCODE_OBS_ENABLED", raising=False)
        data = {"enabled": True}
        settings = ObservabilitySettings.from_dict(data)
        assert settings.enabled is True


class TestSettingsIntegration:
    """测试 Settings.from_toml() 加载 ObservabilitySettings。"""

    def test_from_toml_loads_observability(self, tmp_path):
        """Settings.from_toml 应正确解析 [observability] 段落。"""
        from ohmycode.config.settings import Settings

        toml_content = b"""
[agent]
recursion_limit = 25

[tools]
enabled = []

[observability]
enabled = true
exporter_type = "console"
log_level = "DEBUG"
service_name = "test-ohmycode"
"""
        toml_file = tmp_path / "test.toml"
        toml_file.write_bytes(toml_content)

        settings = Settings.from_toml(toml_file)
        assert settings.observability is not None
        assert settings.observability.enabled is True
        assert settings.observability.exporter_type == "console"
        assert settings.observability.log_level == "DEBUG"
        assert settings.observability.service_name == "test-ohmycode"

    def test_from_toml_missing_observability(self, tmp_path):
        """缺少 [observability] 段落时应使用默认值。"""
        from ohmycode.config.settings import Settings

        toml_content = b"""
[agent]
recursion_limit = 25
"""
        toml_file = tmp_path / "test.toml"
        toml_file.write_bytes(toml_content)

        settings = Settings.from_toml(toml_file)
        assert settings.observability is not None
        assert settings.observability.enabled is False

    def test_from_toml_nonexistent_file(self):
        """TOML 文件不存在时应返回默认值。"""
        from ohmycode.config.settings import Settings
        from pathlib import Path

        settings = Settings.from_toml(Path("/nonexistent.toml"))
        assert settings.observability is None
