"""聊天区域组件 — 显示对话历史和流式回复。"""

from textual.widgets import TextArea


class ChatArea(TextArea):
    """聊天区域，显示对话历史，支持文本选择和复制。

    基于 TextArea(read_only=True)，用户可以：
    - 鼠标拖选文本
    - Ctrl+C 复制选中文本
    - Ctrl+A 全选

    流式输出支持：
    - start_agent_message() → append_agent_token() → finish_agent_message()
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
        self._streaming = False  # 是否正在流式输出中

    def _append(self, text: str) -> None:
        """追加文本并刷新显示。"""
        self._content += text
        self.load_text(self._content)
        self.scroll_end(animate=False)

    def add_user_message(self, text: str) -> None:
        """添加用户消息到聊天记录。"""
        self._append(f"\n你: {text}\n\n")

    def add_agent_message(self, text: str) -> None:
        """一次性添加完整的 Agent 消息（非流式场景）。"""
        self._append(f"\n🤖 {text}\n\n")

    # ===== 流式输出 API =====

    def start_agent_message(self) -> None:
        """开始一次流式 Agent 回复，写入前缀。"""
        if self._streaming:
            return  # 避免重复开始
        self._streaming = True
        self._append("\n🤖 ")

    def append_agent_token(self, token: str) -> None:
        """追加一个 token 到当前流式回复。"""
        if not self._streaming:
            self.start_agent_message()
        self._content += token
        self.load_text(self._content)
        self.scroll_end(animate=False)

    def finish_agent_message(self) -> None:
        """结束当前流式回复。"""
        if not self._streaming:
            return
        self._streaming = False
        self._append("\n\n")
