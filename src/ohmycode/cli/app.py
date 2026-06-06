"""Textual TUI 主应用。"""

from typing import Any

from langchain_core.messages import AIMessage, HumanMessage
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Center, Middle
from textual.screen import ModalScreen
from textual.widgets import Button, Footer, Header, Label, TextArea

from ohmycode.cli.widgets.chat_area import ChatArea
from ohmycode.cli.widgets.input_bar import InputBar
from ohmycode.cli.widgets.status_bar import StatusBar
from ohmycode.cli.widgets.tool_panel import ToolPanel
from ohmycode.types import AgentState


class QuitConfirmScreen(ModalScreen[bool]):
    """退出确认弹窗。"""

    DEFAULT_CSS = """
    QuitConfirmScreen {
        align: center middle;
    }
    #quit-dialog {
        width: 50;
        height: 9;
        border: thick $primary;
        background: $surface;
        padding: 1 2;
    }
    #quit-dialog Label {
        text-align: center;
        width: 100%;
        margin-bottom: 1;
    }
    #quit-buttons {
        width: 100%;
        height: 3;
        layout: horizontal;
        align: center middle;
    }
    #quit-buttons Button {
        margin: 0 1;
        width: 12;
    }
    """

    def compose(self) -> ComposeResult:
        with Center(id="quit-dialog"):
            yield Label("确定要退出 ohmycode 吗？")
            with Middle(id="quit-buttons"):
                yield Button("确定", variant="error", id="quit-confirm-btn")
                yield Button("取消", variant="default", id="quit-cancel-btn")

    async def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "quit-confirm-btn":
            self.dismiss(True)
        else:
            self.dismiss(False)

    def key_escape(self) -> None:
        """按 Esc 关闭弹窗（取消退出）。"""
        self.dismiss(False)


class OhmycodeApp(App[None]):
    """ohmycode Textual TUI 应用。

    提供全功能的终端聊天界面，支持：
    - 逐 token 流式显示 Agent 回复
    - 实时状态栏（空闲/思考中/执行工具中）
    - 工具调用详情面板
    - 键盘快捷键（Ctrl+Q 退出）
    """

    TITLE = "ohmycode"
    CSS_PATH = "styles/app.tcss"

    BINDINGS = [
        Binding("ctrl+q", "quit", "退出", priority=True),
        Binding("escape", "request_quit", "退出", priority=True),
    ]

    def __init__(self, agent_graph: Any, model_name: str = "unknown") -> None:
        super().__init__()
        self.agent_graph = agent_graph
        self.model_name = model_name
        self._conversation: list = []

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        yield ChatArea()
        yield ToolPanel()
        yield StatusBar()
        yield InputBar()
        yield Footer()

    def on_mount(self) -> None:
        """应用启动时聚焦输入框。"""
        self.query_one("#user-input").focus()

    def action_request_quit(self) -> None:
        """弹出退出确认对话框。"""
        def check_quit(confirmed: bool) -> None:
            if confirmed:
                self.exit()

        self.push_screen(QuitConfirmScreen(), check_quit)

    async def on_button_pressed(self) -> None:
        """发送按钮点击事件。"""
        input_widget = self.query_one("#user-input", TextArea)
        text = input_widget.text.strip()
        if text:
            input_widget.clear()
            await self._handle_user_input(text)

    async def _handle_user_input(self, text: str) -> None:
        """处理用户输入：显示消息并启动 Agent。"""
        chat_area = self.query_one(ChatArea)
        chat_area.add_user_message(text)

        self._conversation.append(HumanMessage(content=text))
        self.run_worker(self._run_agent(), exclusive=True)

    async def _run_agent(self) -> None:
        """异步运行 Agent，流式显示回复。"""
        status = self.query_one(StatusBar)
        chat_area = self.query_one(ChatArea)
        tool_panel = self.query_one(ToolPanel)
        input_widget = self.query_one("#user-input", TextArea)

        # 禁用输入
        input_widget.disabled = True
        status.agent_state = AgentState.THINKING

        try:
            full_response = ""
            async for event_name, event_data in self.agent_graph.astream(
                {"messages": self._conversation},
                stream_mode=["messages", "updates"],
                version="v2",
            ):
                if event_name == "messages":
                    # event_data 是 (AIMessageChunk, metadata_dict)
                    if not isinstance(event_data, tuple) or len(event_data) != 2:
                        continue
                    msg, metadata = event_data
                    if (
                        msg
                        and hasattr(msg, "content")
                        and msg.content
                        and metadata.get("langgraph_node") == "agent"
                    ):
                        full_response += msg.content

                elif event_name == "updates":
                    # event_data 是 {node_name: {state_dict}}
                    for node_name, state in event_data.items():
                        if node_name == "tools":
                            status.agent_state = AgentState.EXECUTING
                            messages = state.get("messages", [])
                            for m in messages:
                                if isinstance(m, AIMessage) and m.tool_calls:
                                    for tc in m.tool_calls:
                                        tool_panel.add_tool_call(
                                            tc["name"], tc.get("args", {})
                                        )
                        elif node_name == "agent":
                            status.agent_state = AgentState.THINKING

            # 流式响应结束，写入完整回复
            if full_response:
                chat_area.add_agent_message(full_response)
                self._conversation.append(AIMessage(content=full_response))

        except Exception as e:
            chat_area.add_agent_message(f"[red]错误: {e}[/red]")
        finally:
            status.agent_state = AgentState.IDLE
            input_widget.disabled = False
            input_widget.focus()
