"""工具模块。

通过 Protocol 抽象工具提供者，支持任意扩展。
内置工具通过 ToolDefinition 基类定义，经 build_tool 工厂转换为 LangChain BaseTool。
"""

from ohmycode.tools.base import ToolDefinition, build_tool
from ohmycode.tools.builtins import BuiltinToolProvider
from ohmycode.tools.registry import ToolRegistry

__all__ = ["ToolDefinition", "build_tool", "BuiltinToolProvider", "ToolRegistry"]
