"""Textual TUI 主应用。

包含 OpenTelemetry Tracing 和 Metrics 埋点：
- 每次 _run_agent 创建对话级别 trace
- 追踪完整的用户对话生命周期
- 记录对话延迟和错误指标
"""

import asyncio
import time
import uuid
from typing import Any

from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Center, Middle
from textual.screen import ModalScreen
from textual.widgets import Button, Footer, Header, Label, TextArea

from ohmycode.cli.widgets.approval_dialog import ApprovalDialog
from ohmycode.cli.widgets.chat_area import ChatArea
from ohmycode.cli.widgets.input_bar import InputBar
from ohmycode.cli.widgets.status_bar import StatusBar
from ohmycode.observability.tracing import get_tracer
from ohmycode.observability.metrics import (
    get_conversation_duration,
    record_error,
)
from ohmycode.observability.logging import get_logger
from ohmycode.tools import base as tool_base
from ohmycode.types import AgentState

logger = get_logger(__name__)


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
    - 工具调用详情面板（调用参数 + 返回结果）
    - 键盘快捷键（ESC 退出）
    - OTel Tracing 和 Metrics 埋点
    """

    TITLE = "ohmycode"
    CSS_PATH = "styles/app.tcss"

    BINDINGS = [
        Binding("escape", "request_quit", "退出", priority=True),
    ]

    def __init__(self, agent_graph: Any, model_name: str = "unknown") -> None:
        super().__init__()
        self.agent_graph = agent_graph
        self.model_name = model_name
        self._conversation: list = []
        self._approved_tools: set[str] = set()  # 本次会话已"始终允许"的工具

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        yield ChatArea()
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
        """异步运行 Agent，逐 token 流式显示回复，展示工具调用和思考过程。

        流式处理逻辑：
        1. "messages" 流：AIMessageChunk 的 content → 逐 token 追加到 ChatArea
        2. "updates" 流：
           - node=="agent" → AIMessage 包含 tool_calls 时挂载 ToolCallCard
           - node=="tools" → ToolMessage 更新 ToolCallCard 结果

        包含 OTel Tracing 埋点：
        - 创建对话级别 trace（ohmycode.conversation）
        - 记录对话延迟到 ohmycode.conversation.duration Histogram
        - 记录错误到 ohmycode.errors Counter
        """
        status = self.query_one(StatusBar)
        chat_area = self.query_one(ChatArea)
        input_widget = self.query_one("#user-input", TextArea)

        # 禁用输入
        input_widget.disabled = True
        status.agent_state = AgentState.THINKING

        # 追踪状态
        tool_call_map: dict[str, str] = {}  # tool_call_id → card_id
        full_response = ""
        streaming_started = False

        # ===== OTel 可观测性 =====
        conversation_id = str(uuid.uuid4())[:8]
        start_time = time.monotonic()
        tracer = get_tracer()

        # 注册工具审批回调（直接写入 base 模块变量，避免 import 副本问题）
        app_ref = self

        async def _approval_handler(tool_name: str, args: dict) -> bool:
            """审批回调：检查是否需要弹窗，如需要则等待用户决定。"""
            # 如果该工具已被"始终允许"，直接放行
            if tool_name in app_ref._approved_tools:
                return True

            # 通过 Future 等待弹窗结果
            future: asyncio.Future[bool] = asyncio.get_event_loop().create_future()

            def on_dialog_result(result: bool | tuple) -> None:
                if isinstance(result, tuple) and result == ApprovalDialog.ALWAYS_ALLOW:
                    # 用户选择"始终允许"，记录该工具
                    app_ref._approved_tools.add(tool_name)
                    future.set_result(True)
                elif result is True:
                    future.set_result(True)
                else:
                    future.set_result(False)

            app_ref.push_screen(ApprovalDialog(tool_name, args), on_dialog_result)
            return await future

        tool_base.TOOL_APPROVAL_HANDLER = _approval_handler

        try:
            # 创建对话级别 trace
            with tracer.start_as_current_span(
                "ohmycode.conversation",
                attributes={"conversation.id": conversation_id},
            ) as conv_span:
                logger.info("开始处理对话 conversation_id=%s", conversation_id)

                async for event_name, event_data in self.agent_graph.astream(
                    {"messages": self._conversation},
                    stream_mode=["messages", "updates"],
                    version="v2",
                ):

                    # ===== 实时 token 流 =====
                    if event_name == "messages":
                        if not isinstance(event_data, tuple) or len(event_data) != 2:
                            continue
                        msg, metadata = event_data

                        # 只处理 agent 节点输出的文本内容
                        if (
                            msg
                            and hasattr(msg, "content")
                            and msg.content
                            and metadata.get("langgraph_node") == "agent"
                        ):
                            if not streaming_started:
                                chat_area.start_agent_message()
                                streaming_started = True
                            chat_area.append_agent_token(msg.content)
                            full_response += msg.content

                    # ===== 状态更新流 =====
                    elif event_name == "updates":
                        for node_name, state in event_data.items():

                            if node_name == "agent":
                                status.agent_state = AgentState.THINKING
                                messages = state.get("messages", [])

                                for m in messages:
                                    if not isinstance(m, AIMessage):
                                        continue

                                    # 处理工具调用
                                    if m.tool_calls:
                                        # 先结束当前流式消息（如有）
                                        if streaming_started:
                                            chat_area.finish_agent_message()
                                            streaming_started = False

                                        for tc in m.tool_calls:
                                            card_id = chat_area.mount_tool_card(
                                                tc["name"], tc.get("args", {})
                                            )
                                            tool_call_map[tc.get("id", "")] = card_id

                                    # 如果有文本内容（思考/推理）且流式尚未开始
                                    if m.content and not streaming_started:
                                        chat_area.start_agent_message()
                                        streaming_started = True
                                        chat_area.append_agent_token(m.content)
                                        full_response += m.content

                            elif node_name == "tools":
                                status.agent_state = AgentState.EXECUTING
                                messages = state.get("messages", [])

                                for m in messages:
                                    if isinstance(m, ToolMessage):
                                        call_id = getattr(m, "tool_call_id", "")
                                        card_id = tool_call_map.get(call_id, "")
                                        tool_name = getattr(m, "name", "unknown")
                                        if card_id:
                                            chat_area.update_tool_result(
                                                card_id, m.content
                                            )

                # 流式输出结束
                if streaming_started:
                    chat_area.finish_agent_message()

                # 保存完整回复到对话历史
                if full_response:
                    self._conversation.append(AIMessage(content=full_response))

                # 记录对话完成
                conv_span.set_attribute("response_length", len(full_response))

        except Exception as e:
            chat_area.add_agent_message(f"[red]错误: {e}[/red]")
            # 记录错误指标
            record_error(module="tui", error_type=type(e).__name__)
            logger.error("Agent 运行错误: %s", e, exc_info=True)
        finally:
            # 清除审批回调
            tool_base.TOOL_APPROVAL_HANDLER = None
            status.agent_state = AgentState.IDLE
            input_widget.disabled = False
            input_widget.focus()

            # 记录对话延迟指标
            duration_ms = (time.monotonic() - start_time) * 1000
            try:
                get_conversation_duration().record(
                    duration_ms,
                    attributes={"model": self.model_name},
                )
            except Exception:
                pass  # 静默处理指标记录错误
