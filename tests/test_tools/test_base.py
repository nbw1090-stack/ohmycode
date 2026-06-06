"""测试工具基类、工厂函数和 BuiltinToolProvider。"""

from pydantic import BaseModel

from ohmycode.tools.base import (
    PermissionResult,
    ToolDefinition,
    ValidationResult,
    build_tool,
)
from ohmycode.tools.builtins import BuiltinToolProvider


# ===== 测试用工具定义 =====


class DummyInput(BaseModel):
    text: str


class DummyToolDef(ToolDefinition):
    name = "dummy_test"
    aliases = ["dt"]

    @property
    def is_read_only(self) -> bool:
        return True

    @property
    def is_concurrency_safe(self) -> bool:
        return True

    def description(self) -> str:
        return "A dummy tool for testing."

    def input_schema(self) -> type[BaseModel]:
        return DummyInput

    def execute(self, **kwargs) -> str:
        return f"echo: {kwargs['text']}"


class DenyToolDef(ToolDefinition):
    name = "deny_test"

    def description(self) -> str:
        return "A tool that denies all permissions."

    def input_schema(self) -> type[BaseModel]:
        return DummyInput

    def check_permissions(self, input_data: BaseModel) -> PermissionResult:
        return PermissionResult(behavior="deny", reason="test deny")

    def execute(self, **kwargs) -> str:
        return "should not reach here"


class ValidateFailToolDef(ToolDefinition):
    name = "validate_fail_test"

    def description(self) -> str:
        return "A tool that fails validation."

    def input_schema(self) -> type[BaseModel]:
        return DummyInput

    def validate_input(self, input_data: BaseModel) -> ValidationResult:
        return ValidationResult(is_valid=False, errors=["bad input"])

    def execute(self, **kwargs) -> str:
        return "should not reach here"


class TruncateToolDef(ToolDefinition):
    name = "truncate_test"
    max_result_size = 10

    def description(self) -> str:
        return "A tool that produces long output."

    def input_schema(self) -> type[BaseModel]:
        return DummyInput

    def execute(self, **kwargs) -> str:
        return "A" * 100


# ===== Test: ToolDefinition 默认值 =====


class TestToolDefinitionDefaults:

    def test_default_security_properties(self):
        """未覆盖的安全属性应取 TOOL_DEFAULTS 保守值。"""
        defn = DummyToolDef()
        assert defn.is_enabled is True
        assert defn.is_concurrency_safe is True
        assert defn.is_read_only is True
        assert defn.is_destructive is False

    def test_default_metadata(self):
        """默认元数据值。"""
        defn = DummyToolDef()
        assert defn.name == "dummy_test"
        assert defn.aliases == ["dt"]
        assert defn.max_result_size == 100_000
        assert defn.should_defer is False

    def test_default_methods(self):
        """可选方法应有合理默认值。"""
        defn = DummyToolDef()
        assert defn.prompt_description() == defn.description()
        assert defn.to_classifier_input() == ""
        result = defn.validate_input(DummyInput(text="x"))
        assert result.is_valid is True
        perm = defn.check_permissions(DummyInput(text="x"))
        assert perm.behavior == "allow"


# ===== Test: build_tool 工厂 =====


class TestBuildTool:

    def test_produces_structured_tool(self):
        """build_tool 应产出 LangChain StructuredTool。"""
        from langchain_core.tools import BaseTool

        tool = build_tool(DummyToolDef())
        assert isinstance(tool, BaseTool)
        assert tool.name == "dummy_test"

    def test_execute_passes_through(self):
        """正常工具应成功执行并返回结果。"""
        tool = build_tool(DummyToolDef())
        result = tool.invoke({"text": "hello"})
        assert result == "echo: hello"

    def test_permission_denied(self):
        """权限检查拒绝时返回错误消息。"""
        tool = build_tool(DenyToolDef())
        result = tool.invoke({"text": "hello"})
        assert "权限被拒绝" in result
        assert "test deny" in result

    def test_validation_failure(self):
        """输入验证失败时返回错误消息。"""
        tool = build_tool(ValidateFailToolDef())
        result = tool.invoke({"text": "hello"})
        assert "输入验证失败" in result
        assert "bad input" in result

    def test_result_truncation(self):
        """结果超过 max_result_size 时应截断。"""
        tool = build_tool(TruncateToolDef())
        result = tool.invoke({"text": "x"})
        assert len(result) < 100
        assert "截断" in result

    def test_empty_name_raises(self):
        """name 为空时应抛出 ValueError。"""
        class NoName(ToolDefinition):
            def description(self): return "x"
            def input_schema(self): return DummyInput
            def execute(self, **kwargs): return "x"

        try:
            build_tool(NoName())
            assert False, "应抛出 ValueError"
        except ValueError:
            pass


# ===== Test: BuiltinToolProvider =====


class TestBuiltinToolProvider:

    def test_returns_all_tools(self):
        """默认应返回所有已注册工具。"""
        provider = BuiltinToolProvider()
        tools = provider.tools()
        names = {t.name for t in tools}
        assert "read_file" in names
        assert "write_file" in names
        assert "list_files" in names
        assert "execute_command" in names
        assert "search_files" in names
        assert "echo" in names

    def test_filters_enabled_tools(self):
        """指定 enabled 时只返回对应工具。"""
        provider = BuiltinToolProvider(enabled=["echo", "read_file"])
        tools = provider.tools()
        names = {t.name for t in tools}
        assert names == {"echo", "read_file"}

    def test_ignores_unknown_enabled(self):
        """enabled 中不存在的工具名应被忽略。"""
        provider = BuiltinToolProvider(enabled=["echo", "nonexistent"])
        tools = provider.tools()
        assert len(tools) == 1
        assert tools[0].name == "echo"

    def test_tool_names_property(self):
        """tool_names 属性应返回所有可用工具名。"""
        provider = BuiltinToolProvider()
        names = provider.tool_names
        assert "read_file" in names
        assert len(names) >= 6

    def test_tools_are_base_tool(self):
        """所有工具应是 LangChain BaseTool 实例。"""
        from langchain_core.tools import BaseTool

        provider = BuiltinToolProvider()
        for tool in provider.tools():
            assert isinstance(tool, BaseTool)

    def test_implements_tool_provider_protocol(self):
        """BuiltinToolProvider 应满足 ToolProvider 协议。"""
        from ohmycode.tools.protocols import ToolProvider

        provider = BuiltinToolProvider()
        assert isinstance(provider, ToolProvider)
