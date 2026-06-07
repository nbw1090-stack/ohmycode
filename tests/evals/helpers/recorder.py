"""工具调用记录器 — 从 graph.astream() 事件流中捕获所有工具调用。

不使用 monkeypatch，而是从 LangGraph 的 stream 事件中
提取 AIMessage.tool_calls 和 ToolMessage。
"""

from dataclasses import dataclass, field

from langchain_core.messages import AIMessage, HumanMessage, ToolMessage


@dataclass
class RecordedToolCall:
    """记录一次工具调用的完整信息。"""

    name: str
    args: dict
    result: str = ""
    tool_call_id: str = ""


class ToolCallRecorder:
    """从 graph stream 事件中记录所有工具调用。"""

    def __init__(self) -> None:
        self.calls: list[RecordedToolCall] = []
        self._pending_calls: dict[str, RecordedToolCall] = {}

    def process_stream_event(self, event_name: str, event_data: tuple) -> None:
        """处理一个 stream 事件。

        从 LangGraph v2 astream 的 ("messages", (message_chunk, metadata)) 事件中
        提取工具调用和工具结果。
        """
        if event_name != "messages":
            return

        if not isinstance(event_data, tuple) or len(event_data) < 2:
            return

        message, _metadata = event_data

        # 检测 AIMessage 中的 tool_calls
        if isinstance(message, AIMessage):
            tool_calls = getattr(message, "tool_calls", None)
            if tool_calls:
                for tc in tool_calls:
                    call = RecordedToolCall(
                        name=tc.get("name", ""),
                        args=tc.get("args", {}),
                        tool_call_id=tc.get("id", ""),
                    )
                    self.calls.append(call)
                    self._pending_calls[call.tool_call_id] = call

        # 检测 ToolMessage 中的工具结果
        if isinstance(message, ToolMessage):
            tool_call_id = getattr(message, "tool_call_id", "")
            if tool_call_id in self._pending_calls:
                self._pending_calls[tool_call_id].result = str(message.content)
                del self._pending_calls[tool_call_id]
            else:
                # 没有匹配的 pending call，单独记录
                self.calls.append(
                    RecordedToolCall(
                        name=getattr(message, "name", "unknown"),
                        args={},
                        result=str(message.content),
                        tool_call_id=tool_call_id,
                    )
                )

    def process_update_event(self, node_name: str, state_update: dict) -> None:
        """处理 "updates" stream 事件中的消息。

        从 state_update["messages"] 中提取完整消息。
        对于已有记录的 tool call，用完整的 args 覆盖。
        """
        messages = state_update.get("messages", [])
        if not messages:
            return

        for message in messages:
            if isinstance(message, AIMessage):
                tool_calls = getattr(message, "tool_calls", None)
                if tool_calls:
                    for tc in tool_calls:
                        call_id = tc.get("id", "")
                        # 如果已有记录（来自 messages stream），用完整 args 更新
                        existing = next(
                            (c for c in self.calls if c.tool_call_id == call_id),
                            None,
                        )
                        if existing:
                            # 更新 args（stream chunks 可能 args 为空，update 有完整 args）
                            tc_args = tc.get("args", {})
                            if tc_args:
                                existing.args = tc_args
                        else:
                            # 新记录
                            call = RecordedToolCall(
                                name=tc.get("name", ""),
                                args=tc.get("args", {}),
                                tool_call_id=call_id,
                            )
                            self.calls.append(call)
                            self._pending_calls[call_id] = call

            elif isinstance(message, ToolMessage):
                tool_call_id = getattr(message, "tool_call_id", "")
                if tool_call_id in self._pending_calls:
                    self._pending_calls[tool_call_id].result = str(message.content)
                    del self._pending_calls[tool_call_id]

    @property
    def tool_names(self) -> list[str]:
        """返回所有调用的工具名称列表（按调用顺序）。"""
        return [c.name for c in self.calls]

    def find(self, name: str) -> list[RecordedToolCall]:
        """查找指定名称的所有工具调用。"""
        return [c for c in self.calls if c.name == name]

    def clear(self) -> None:
        """清空所有记录。"""
        self.calls.clear()
        self._pending_calls.clear()


async def run_agent_turn(
    graph,
    recorder: ToolCallRecorder,
    user_input: str,
    conversation: list | None = None,
) -> str:
    """运行一轮 agent 对话，记录所有工具调用，返回最终文本回复。

    Args:
        graph: 编译后的 LangGraph 图
        recorder: 工具调用记录器
        user_input: 用户输入文本
        conversation: 已有的对话消息列表（可追加新消息）

    Returns:
        agent 的最终文本回复
    """
    from langchain_core.messages import HumanMessage

    if conversation is None:
        conversation = []

    conversation.append(HumanMessage(content=user_input))

    final_text = ""

    async for event_name, event_data in graph.astream(
        {"messages": conversation},
        stream_mode=["messages", "updates"],
        version="v2",
    ):
        if event_name == "messages":
            recorder.process_stream_event(event_name, event_data)
            # 提取文本 token
            message, _metadata = event_data
            if hasattr(message, "content") and isinstance(message.content, str) and message.content:
                # AIMessageChunk 的增量文本
                if hasattr(message, "tool_calls") and message.tool_calls:
                    pass  # 工具调用消息，跳过文本收集
                else:
                    final_text += message.content

        elif event_name == "updates":
            for node_name, state_update in event_data.items():
                if isinstance(state_update, dict):
                    recorder.process_update_event(node_name, state_update)
                    # 从 updates 中获取完整消息用于 conversation
                    msgs = state_update.get("messages", [])
                    for msg in msgs:
                        if msg not in conversation:
                            conversation.append(msg)

    return final_text.strip()


async def run_multi_turn(
    graph,
    recorder: ToolCallRecorder,
    turns: list[str],
) -> list[str]:
    """运行多轮对话，返回每轮的回复。"""
    conversation: list = []
    responses: list[str] = []

    for user_input in turns:
        recorder.clear()
        response = await run_agent_turn(graph, recorder, user_input, conversation)
        responses.append(response)

    return responses
