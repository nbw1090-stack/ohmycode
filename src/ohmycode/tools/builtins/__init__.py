"""内置工具提供者 — 从定义列表收集所有内置工具。

每个工具在对应的模块中定义，此处统一收集并通过 build_tool 工厂转换为
LangChain StructuredTool 实例。
"""

from langchain_core.tools import BaseTool

from ohmycode.tools.base import build_tool
from ohmycode.tools.builtins.echo import EchoDef
from ohmycode.tools.builtins.execute_command import ExecuteCommandDef
from ohmycode.tools.builtins.list_files import ListFilesDef
from ohmycode.tools.builtins.read_file import ReadFileDef
from ohmycode.tools.builtins.search_files import SearchFilesDef
from ohmycode.tools.builtins.write_file import WriteFileDef

# ===== 工具定义列表 =====
# 新增工具只需在此列表添加对应的 Def 实例
_TOOL_DEFINITIONS = [
    ReadFileDef(),
    WriteFileDef(),
    ListFilesDef(),
    ExecuteCommandDef(),
    SearchFilesDef(),
    EchoDef(),
]


class BuiltinToolProvider:
    """内置工具提供者，实现 ToolProvider 协议。

    通过列表注册的方式管理所有内置工具。
    新增工具只需：
    1. 在 builtins/ 下创建新模块定义 ToolDefinition 子类
    2. 在此文件导入并添加到 _TOOL_DEFINITIONS 列表
    """

    def __init__(self, enabled: list[str] | None = None) -> None:
        """初始化工具提供者。

        Args:
            enabled: 允许的工具名称列表。为 None 时返回所有已启用的工具。
        """
        self._definitions = {
            defn.name: defn for defn in _TOOL_DEFINITIONS if defn.is_enabled
        }
        self._enabled = enabled

    def tools(self) -> list[BaseTool]:
        """返回启用的工具列表（LangChain BaseTool 实例）。"""
        if self._enabled is None:
            names = list(self._definitions.keys())
        else:
            names = [n for n in self._enabled if n in self._definitions]

        return [build_tool(self._definitions[n]) for n in names]

    @property
    def tool_names(self) -> list[str]:
        """返回所有可用的工具名称。"""
        return list(self._definitions.keys())
