"""聊天区域组件 — 显示对话历史、流式回复和内联工具调用卡片。

基于 VerticalScroll 容器，内部按顺序挂载：
- MessageBlock: 用户/Agent 消息
- ToolCallCard: 可折叠的工具调用详情

流式输出时只刷新当前 MessageBlock widget，不重建整个容器，消除闪屏。
"""

from textual.containers import VerticalScroll

from ohmycode.cli.widgets.message_block import MessageBlock
from ohmycode.cli.widgets.tool_card import ToolCallCard


class ChatArea(VerticalScroll):
    """对话流容器，支持流式回复和内联折叠工具卡片。

    公开 API（保持与旧版兼容）：
    - add_user_message(text) → 添加用户消息
    - add_agent_message(text) → 添加完整 Agent 消息（非流式）
    - start_agent_message() → 开始流式 Agent 回复
    - append_agent_token(token) → 追加一个 token
    - finish_agent_message() → 结束流式回复
    - mount_tool_card(name, args) → 挂载工具调用卡片，返回 card_id
    - update_tool_result(card_id, result) → 更新工具调用结果
    """

    DEFAULT_CSS = """
    ChatArea {
        height: 1fr;
        border: solid $primary;
        padding: 0 1;
    }
    """

    def __init__(self) -> None:
        super().__init__(id="chat-log")
        self._streaming_block: MessageBlock | None = None
        self._card_counter = 0

    # ===== 基础消息 =====

    def add_user_message(self, text: str) -> None:
        """添加用户消息到对话流。"""
        block = MessageBlock(role="user", content=text)
        self.mount(block)
        self.call_after_refresh(self.scroll_end, animate=False)

    def add_agent_message(self, text: str) -> None:
        """一次性添加完整的 Agent 消息（非流式场景）。"""
        block = MessageBlock(role="agent", content=text)
        self.mount(block)
        self.call_after_refresh(self.scroll_end, animate=False)

    # ===== 流式输出 API =====

    def start_agent_message(self) -> None:
        """开始一次流式 Agent 回复，创建新的 MessageBlock。"""
        if self._streaming_block is not None:
            return  # 避免重复开始
        block = MessageBlock(role="agent")
        self.mount(block)
        self._streaming_block = block

    def append_agent_token(self, token: str) -> None:
        """追加一个 token 到当前流式回复。

        只刷新当前 MessageBlock widget，不重建整个容器。
        """
        if self._streaming_block is None:
            self.start_agent_message()
        self._streaming_block.append(token)
        self.scroll_end(animate=False)

    def finish_agent_message(self) -> None:
        """结束当前流式回复。"""
        self._streaming_block = None

    # ===== 工具调用卡片 =====

    def mount_tool_card(self, tool_name: str, args: dict) -> str:
        """挂载一个折叠的工具调用卡片到对话流。

        Args:
            tool_name: 工具名称
            args: 工具调用参数

        Returns:
            card_id: 用于后续 update_tool_result() 更新结果
        """
        self._card_counter += 1
        card_id = f"tool-card-{self._card_counter}"
        card = ToolCallCard(
            tool_name=tool_name,
            args=args,
            card_id=card_id,
        )
        self.mount(card)
        self.call_after_refresh(self.scroll_end, animate=False)
        return card_id

    def update_tool_result(self, card_id: str, result: str) -> None:
        """更新工具调用卡片的结果。

        Args:
            card_id: mount_tool_card() 返回的标识符
            result: 工具返回结果文本
        """
        try:
            card = self.query_one(f"#{card_id}", ToolCallCard)
            card.set_result(result)
        except Exception:
            pass  # 卡片可能尚未挂载
