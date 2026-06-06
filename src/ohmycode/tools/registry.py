"""工具注册表，管理所有可用的 LangChain 工具。"""

from langchain_core.tools import BaseTool


class ToolRegistry:
    """工具注册表。

    负责收集和管理所有注册的 LangChain 工具实例。
    支持按名称注册、查询和列举。
    """

    def __init__(self) -> None:
        self._tools: dict[str, BaseTool] = {}

    def register(self, tool: BaseTool) -> None:
        """注册一个工具。如果同名工具已存在则覆盖。"""
        self._tools[tool.name] = tool

    def register_all(self, tools: list[BaseTool]) -> None:
        """批量注册工具。"""
        for tool in tools:
            self.register(tool)

    def get(self, name: str) -> BaseTool:
        """按名称获取工具，不存在则抛出 KeyError。"""
        return self._tools[name]

    def get_all(self) -> list[BaseTool]:
        """返回所有已注册的工具列表。"""
        return list(self._tools.values())

    @property
    def names(self) -> list[str]:
        """返回所有已注册的工具名称列表。"""
        return list(self._tools.keys())
