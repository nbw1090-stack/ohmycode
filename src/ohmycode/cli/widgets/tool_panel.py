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
        self._call_counter = 0  # 调用序号，匹配调用和结果

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
        tool_log.scroll_end(animate=False)

    def add_tool_call(self, tool_name: str, args: dict) -> int:
        """记录一次工具调用，返回调用序号。

        Args:
            tool_name: 工具名称
            args: 工具调用参数

        Returns:
            调用序号（用于匹配结果）
        """
        self._call_counter += 1
        args_str = ", ".join(f"{k}={v!r}" for k, v in args.items())
        self._append(f"  #{self._call_counter} → {tool_name}({args_str})\n")
        return self._call_counter

    def add_tool_result(self, call_seq: int, tool_name: str, result: str) -> None:
        """记录工具调用的返回结果。

        Args:
            call_seq: 调用序号（来自 add_tool_call 的返回值）
            tool_name: 工具名称
            result: 工具返回结果文本
        """
        display = result[:200] + "..." if len(result) > 200 else result
        self._append(f"  #{call_seq} ← {tool_name}: {display}\n")

    def reset(self) -> None:
        """清空面板内容（新对话时调用）。"""
        self._content = ""
        self._call_counter = 0
        tool_log = self.query_one("#tool-log", TextArea)
        tool_log.load_text("")
