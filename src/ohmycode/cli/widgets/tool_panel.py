"""工具面板组件 — 展示工具调用详情，支持文本选择和复制。"""

from textual.widgets import Collapsible, TextArea


class ToolPanel(Collapsible):
    """工具调用展示面板（可折叠）。

    显示 Agent 调用工具的名称、参数和返回结果。
    支持文本选择和 Ctrl+C 复制。
    """

    DEFAULT_CSS = """
    ToolPanel {
        height: auto;
        max-height: 12;
        border: solid $warning;
    }
    ToolPanel > TextArea {
        height: auto;
        max-height: 10;
    }
    """

    def __init__(self) -> None:
        super().__init__(title="🔧 工具调用", id="tool-panel")
        self._content = ""

    def compose(self):
        yield TextArea(
            "",
            read_only=True,
            show_line_numbers=False,
            id="tool-log",
        )

    def _append(self, text: str) -> None:
        """追加文本并刷新显示。"""
        self._content += text
        tool_log = self.query_one("#tool-log", TextArea)
        tool_log.load_text(self._content)

    def add_tool_call(self, tool_name: str, args: dict) -> None:
        """记录一次工具调用。"""
        args_str = ", ".join(f"{k}={v!r}" for k, v in args.items())
        self._append(f"→ 调用工具: {tool_name}({args_str})\n")

    def add_tool_result(self, tool_name: str, result: str) -> None:
        """记录工具调用的返回结果。"""
        display = result[:200] + "..." if len(result) > 200 else result
        self._append(f"← 工具结果: {tool_name}: {display}\n")
