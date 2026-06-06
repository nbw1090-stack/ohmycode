"""消息块组件 — 对话流中的单条消息。

每条消息是独立的 Static widget，流式输出时只刷新此 widget，
不会重建整个对话容器，从而消除闪屏。
"""

from rich.text import Text
from textual.widgets import Static


class MessageBlock(Static):
    """对话流中的单条消息。

    内部使用 Rich Text 对象累积内容，通过 append() 逐 token 追加，
    每次只调用 self.update() 刷新自身，不影响其他消息块。

    Attributes:
        role: 消息角色 — "user" 或 "agent"
    """

    DEFAULT_CSS = """
    MessageBlock {
        height: auto;
        width: 100%;
        padding: 0 1;
    }
    """

    def __init__(
        self, role: str, content: str = "", id: str | None = None
    ) -> None:
        """初始化消息块。

        Args:
            role: "user" 或 "agent"
            content: 初始内容（可为空，后续通过 append 追加）
            id: 可选 widget id
        """
        self.role = role
        self._text = Text(content)
        prefix = "你: " if role == "user" else "🤖 "
        self._prefix = Text(prefix)
        super().__init__(self._prefix + self._text, id=id)

    def append(self, text: str) -> None:
        """追加文本到消息末尾并刷新显示。

        Args:
            text: 要追加的文本（通常是单个 token）
        """
        self._text.append(text)
        self.update(self._prefix + self._text)
