"""Agent 状态定义。

直接使用 LangGraph 内置的 MessagesState，无需扩展。
未来如需额外状态字段（如 tool_call_count），可在此处扩展。
"""

from langgraph.graph import MessagesState

__all__ = ["MessagesState"]
