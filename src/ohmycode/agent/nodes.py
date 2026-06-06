"""LangGraph Agent 节点函数。

定义 ReAct 循环中的核心节点：
- call_model: 调用 LLM 生成回复
- should_continue: 路由函数，判断是否需要执行工具
"""

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, SystemMessage
from langgraph.graph import MessagesState


def make_call_model(system_prompt: str, model: BaseChatModel):
    """创建 call_model 节点函数。

    工厂模式：返回一个闭包，捕获 system_prompt 和 model。
    每次调用时将系统提示词注入消息列表开头。

    Args:
        system_prompt: 组装好的系统提示词
        model: 配置好的 LangChain ChatModel（已绑定工具）

    Returns:
        async call_model 节点函数
    """

    async def call_model(state: MessagesState) -> dict:
        messages = state["messages"]
        # 确保系统提示词在消息列表开头
        if not messages or not isinstance(messages[0], SystemMessage):
            messages = [SystemMessage(content=system_prompt)] + list(messages)
        response = await model.ainvoke(messages)
        return {"messages": [response]}

    return call_model


def should_continue(state: MessagesState) -> str:
    """路由函数：判断 Agent 是否需要执行工具。

    如果最后一条 AI 消息包含 tool_calls，路由到 "tools" 节点。
    否则结束循环（返回 "__end__"）。

    Args:
        state: 当前图状态

    Returns:
        "tools" 或 "__end__"
    """
    last_message = state["messages"][-1]
    if isinstance(last_message, AIMessage) and last_message.tool_calls:
        return "tools"
    return "__end__"
