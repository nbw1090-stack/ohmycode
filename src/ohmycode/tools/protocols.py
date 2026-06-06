"""工具提供者协议定义。"""

from typing import Protocol, runtime_checkable

from langchain_core.tools import BaseTool


@runtime_checkable
class ToolProvider(Protocol):
    """工具提供者协议。

    任何模块都可以实现此协议来向 Agent 注册工具。
    """

    def tools(self) -> list[BaseTool]:
        """返回要注册的 LangChain 工具列表。"""
        ...
