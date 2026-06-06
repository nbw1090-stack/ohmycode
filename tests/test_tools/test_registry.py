"""工具注册表测试。"""

from langchain_core.tools import tool

from ohmycode.tools.registry import ToolRegistry


class TestToolRegistry:

    def test_register_and_get(self):
        """注册工具后可以通过名称获取。"""
        registry = ToolRegistry()

        @tool
        def test_tool(x: int) -> int:
            """A test tool."""
            return x

        registry.register(test_tool)
        assert registry.get("test_tool") is test_tool

    def test_register_all(self):
        """批量注册多个工具。"""
        registry = ToolRegistry()

        @tool
        def tool_a(x: int) -> int:
            """Tool A."""
            return x

        @tool
        def tool_b(y: str) -> str:
            """Tool B."""
            return y

        registry.register_all([tool_a, tool_b])
        assert len(registry.get_all()) == 2
        assert set(registry.names) == {"tool_a", "tool_b"}

    def test_get_nonexistent_raises(self):
        """获取不存在的工具应抛出 KeyError。"""
        registry = ToolRegistry()
        try:
            registry.get("nonexistent")
            assert False, "应该抛出 KeyError"
        except KeyError:
            pass

    def test_empty_registry(self):
        """空注册表应返回空列表。"""
        registry = ToolRegistry()
        assert registry.get_all() == []
        assert registry.names == []
