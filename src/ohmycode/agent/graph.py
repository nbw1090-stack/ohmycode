"""LangGraph StateGraph 构建器。

构建 ReAct (Reason-Act-Observe) 循环：
  START → agent → should_continue → tools → agent → ... → END

使用 LangGraph 的 StateGraph + MessagesState + ToolNode 实现。
"""

from langchain_core.language_models import BaseChatModel
from langchain_core.tools import BaseTool
from langgraph.graph import END, START, MessagesState, StateGraph
from langgraph.prebuilt import ToolNode

from ohmycode.agent.nodes import make_call_model, should_continue


def build_react_graph(
    model: BaseChatModel,
    tools: list[BaseTool],
    system_prompt: str,
) -> "CompiledGraph":
    """构建 ReAct Agent 图。

    图结构：
        START → agent → should_continue ─┬→ tools → agent (循环)
                                         └→ END

    Args:
        model: 已配置的 LangChain ChatModel
        tools: 可用的 LangChain 工具列表
        system_prompt: 组装好的系统提示词

    Returns:
        编译后的 LangGraph 图，可调用 .invoke() 或 .astream()
    """
    call_model = make_call_model(system_prompt, model)
    tool_node = ToolNode(tools)

    builder = StateGraph(MessagesState)

    # 添加节点
    builder.add_node("agent", call_model)
    builder.add_node("tools", tool_node)

    # 添加边
    builder.add_edge(START, "agent")
    builder.add_conditional_edges("agent", should_continue)
    builder.add_edge("tools", "agent")

    return builder.compile()
