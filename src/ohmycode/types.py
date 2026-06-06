"""共享类型和枚举定义。"""

from enum import Enum


class AgentState(str, Enum):
    """Agent 状态枚举，用于 TUI 状态栏显示。"""
    IDLE = "idle"
    THINKING = "thinking"
    EXECUTING = "executing"
