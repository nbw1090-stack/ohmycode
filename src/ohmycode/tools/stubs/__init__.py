"""桩工具提供者，提供内置的示例工具。"""

from langchain_core.tools import BaseTool

from ohmycode.tools.protocols import ToolProvider
from ohmycode.tools.stubs.echo import echo
from ohmycode.tools.stubs.list_files import list_files
from ohmycode.tools.stubs.read_file import read_file


class StubToolProvider:
    """提供内置的桩工具集合。

    实现 ToolProvider 协议，返回所有桩工具。
    可通过 config/tools.toml 的 enabled 字段过滤启用的工具。
    """

    def __init__(self, enabled: list[str] | None = None) -> None:
        self._all_tools: dict[str, BaseTool] = {
            "echo": echo,
            "read_file": read_file,
            "list_files": list_files,
        }
        self._enabled = enabled

    def tools(self) -> list[BaseTool]:
        """返回启用的工具列表。"""
        if self._enabled is None:
            return list(self._all_tools.values())
        return [self._all_tools[name] for name in self._enabled if name in self._all_tools]
