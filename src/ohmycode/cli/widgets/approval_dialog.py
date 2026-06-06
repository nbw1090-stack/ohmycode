"""工具审批弹窗 — 破坏性工具执行前的用户确认对话框。

当 Agent 试图调用破坏性工具（write_file、execute_command 等）时，
暂停执行并弹出此对话框，等待用户选择允许/拒绝/始终允许。
"""

from textual.app import ComposeResult
from textual.containers import Center, Horizontal, Middle, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Label


class ApprovalDialog(ModalScreen[bool]):
    """工具执行审批弹窗。

    显示工具名称和参数，提供三个选项：
    - 允许：执行本次调用
    - 拒绝：取消本次调用
    - 始终允许：本次会话内该工具不再弹出审批

    Attributes:
        tool_name: 工具名称
        tool_args: 工具调用参数
    """

    # "始终允许" 结果的哨兵值，用 tuple 区分单次允许
    ALWAYS_ALLOW = ("always", True)

    DEFAULT_CSS = """
    ApprovalDialog {
        align: center middle;
    }
    #approval-dialog {
        width: 60;
        max-height: 20;
        border: thick $warning;
        background: $surface;
        padding: 1 2;
    }
    #approval-dialog Label {
        text-align: left;
        width: 100%;
    }
    #approval-title {
        text-style: bold;
        margin-bottom: 1;
    }
    #approval-detail {
        margin-bottom: 1;
        color: $text-muted;
    }
    #approval-buttons {
        width: 100%;
        height: 3;
        layout: horizontal;
        align: center middle;
    }
    #approval-buttons Button {
        margin: 0 1;
    }
    """

    def __init__(
        self,
        tool_name: str,
        tool_args: dict,
    ) -> None:
        super().__init__()
        self.tool_name = tool_name
        self.tool_args = tool_args

    def compose(self) -> ComposeResult:
        with Center(id="approval-dialog"):
            yield Label("⚠️ 工具执行审批", id="approval-title")

            # 格式化工具参数
            detail_lines = [f"工具: {self.tool_name}"]
            for k, v in self.tool_args.items():
                val_str = repr(v)
                if len(val_str) > 120:
                    val_str = val_str[:120] + "..."
                detail_lines.append(f"  {k} = {val_str}")
            yield Label("\n".join(detail_lines), id="approval-detail")

            with Middle(id="approval-buttons"):
                yield Button("允许", variant="success", id="btn-approve")
                yield Button("始终允许", variant="primary", id="btn-always")
                yield Button("拒绝", variant="error", id="btn-deny")

    async def on_button_pressed(self, event: Button.Pressed) -> None:
        match event.button.id:
            case "btn-approve":
                self.dismiss(True)
            case "btn-always":
                self.dismiss(self.ALWAYS_ALLOW)  # type: ignore[arg-type]
            case "btn-deny":
                self.dismiss(False)

    def key_escape(self) -> None:
        """按 Esc 默认拒绝。"""
        self.dismiss(False)
