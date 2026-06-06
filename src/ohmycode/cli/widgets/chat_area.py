"""聊天区域组件 — 显示对话历史和流式回复。"""

from textual.widgets import Static, TextArea


class ChatArea(TextArea):
    """聊天区域，显示对话历史，支持文本选择和复制。

    基于 TextArea(read_only=True)，用户可以：
    - 鼠标拖选文本
    - Ctrl+C 复制选中文本
    - Ctrl+A 全选
    """

    DEFAULT_CSS = """
    ChatArea {
        height: 1fr;
        border: solid $primary;
        padding: 0 1;
    }

    ChatArea .text-area--cursor-line {
        background: transparent;
    }
    """

    def __init__(self) -> None:
        super().__init__(
            "",
            read_only=True,
            show_line_numbers=False,
            id="chat-log",
        )
        self._content = ""

    def _append(self, text: str) -> None:
        """追加文本并刷新显示。"""
        self._content += text
        self.load_text(self._content)
        # 滚动到底部
        self.scroll_end(animate=False)

    def add_user_message(self, text: str) -> None:
        """添加用户消息到聊天记录。"""
        self._append(f"[bold cyan]你:[/] {text}\n\n")

    def add_agent_message(self, text: str) -> None:
        """添加 Agent 消息到聊天记录。"""
        self._append(f"[bold green]助手:[/] {text}\n\n")
