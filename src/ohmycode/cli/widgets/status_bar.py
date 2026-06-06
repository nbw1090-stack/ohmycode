"""状态栏组件 — 显示 Agent 当前状态。"""

from textual.reactive import reactive
from textual.widgets import Static

from ohmycode.types import AgentState

STATE_DISPLAY = {
    AgentState.IDLE: ("● 空闲", "white"),
    AgentState.THINKING: ("◉ 思考中...", "yellow"),
    AgentState.EXECUTING: ("⚙ 执行工具中...", "cyan"),
}


class StatusBar(Static):
    """Agent 状态指示栏。

    显示当前 Agent 是空闲、思考中还是执行工具中。
    使用 reactive 属性自动更新 UI。
    """

    DEFAULT_CSS = """
    StatusBar {
        height: 1;
        padding: 0 1;
        background: $primary-background;
        color: $text;
    }
    """

    agent_state: reactive[AgentState] = reactive(AgentState.IDLE)

    def watch_agent_state(self, new_state: AgentState) -> None:
        """当 agent_state 变化时自动更新显示。"""
        text, color = STATE_DISPLAY.get(new_state, ("● 未知", "white"))
        self.update(f"[{color}]{text}[/]")
