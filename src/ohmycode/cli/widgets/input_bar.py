"""输入栏组件 — 用户输入框和发送按钮。"""

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal
from textual.widgets import Button, TextArea

from textual.events import Key


class InputBar(Horizontal):
    """输入栏，包含文本输入框和发送按钮。

    用户可以按 Enter 键或点击发送按钮提交消息。
    支持 Ctrl+V 粘贴、多行输入。
    """

    DEFAULT_CSS = """
    InputBar {
        height: 5;
        padding: 0 1;
    }

    InputBar > TextArea {
        width: 1fr;
        height: 3;
    }

    InputBar > Button {
        width: 10;
        margin-left: 1;
        height: 3;
    }
    """

    BINDINGS = [
        Binding("enter", "submit", "发送", priority=True),
    ]

    def compose(self) -> ComposeResult:
        yield TextArea(id="user-input")
        yield Button("发送", variant="primary", id="send-btn")

    def action_submit(self) -> None:
        """按 Enter 时提交消息。"""
        input_widget = self.query_one("#user-input", TextArea)
        text = input_widget.text.strip()
        if text:
            input_widget.clear()
            # 通过 app 处理提交
            app = self.app
            from ohmycode.cli.app import OhmycodeApp
            if isinstance(app, OhmycodeApp):
                app.run_worker(app._handle_user_input(text), exclusive=False)
