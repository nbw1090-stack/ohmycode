"""Agent 图测试。"""

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from ohmycode.agent.nodes import should_continue


class TestShouldContinue:

    def test_routes_to_tools_when_tool_calls(self):
        """当 AI 消息包含 tool_calls 时应路由到 'tools'。"""
        state = {
            "messages": [
                HumanMessage(content="hello"),
                AIMessage(
                    content="",
                    tool_calls=[{"name": "echo", "args": {"text": "hi"}, "id": "1"}],
                ),
            ]
        }
        assert should_continue(state) == "tools"

    def test_routes_to_end_when_no_tool_calls(self):
        """当 AI 消息不包含 tool_calls 时应结束。"""
        state = {
            "messages": [
                HumanMessage(content="hello"),
                AIMessage(content="Hi there!"),
            ]
        }
        assert should_continue(state) == "__end__"
