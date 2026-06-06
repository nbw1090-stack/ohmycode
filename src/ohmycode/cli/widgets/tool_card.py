"""工具调用卡片组件 — 对话流中的可折叠工具调用详情。

以折叠状态内联在对话流中，标题显示工具名和参数摘要。
点击展开后显示完整的调用参数和返回结果。
"""

from textual.widgets import Collapsible, Static


class ToolCallCard(Collapsible):
    """对话流中的可折叠工具调用卡片。

    默认折叠，只显示一行摘要如 "🔧 read_file(path="README.md")"。
    展开后显示完整的参数和返回结果。

    Attributes:
        tool_name: 工具名称
        card_id: 唯一标识符，用于查找和更新
    """

    DEFAULT_CSS = """
    ToolCallCard {
        height: auto;
        margin: 0 2;
        background: $boost;
        border: round $primary-muted;
    }
    ToolCallCard > Contents {
        max-height: 15;
        overflow-y: auto;
    }
    ToolCallCard > Contents > Static {
        padding: 0 1;
    }
    """

    # 结果最大显示长度
    MAX_RESULT_DISPLAY = 2000

    def __init__(
        self,
        tool_name: str,
        args: dict,
        card_id: str,
    ) -> None:
        """初始化工具调用卡片。

        Args:
            tool_name: 工具名称
            args: 工具调用参数
            card_id: 唯一标识符
        """
        self.tool_name = tool_name
        self.card_id = card_id
        self._args = args
        self._result: str | None = None

        # 构建标题：工具名(参数摘要)
        args_str = ", ".join(f"{k}={v!r}" for k, v in args.items())
        title = f"🔧 {tool_name}({args_str})"

        super().__init__(title=title, collapsed=True, id=card_id)

    def compose(self):
        """卡片展开后的内容区域。"""
        # 初始显示参数详情
        args_lines = [f"[bold]工具:[/bold] {self.tool_name}"]
        if self._args:
            args_lines.append("[bold]参数:[/bold]")
            for k, v in self._args.items():
                args_lines.append(f"  {k} = {v!r}")
        args_lines.append("")  # 留空行等待结果
        yield Static("\n".join(args_lines), id=f"card-body-{self.card_id}")

    def set_result(self, result_text: str) -> None:
        """设置工具调用的返回结果，更新卡片内容。

        Args:
            result_text: 工具返回的结果文本
        """
        self._result = result_text

        # 截断超长结果
        display = result_text
        if len(display) > self.MAX_RESULT_DISPLAY:
            display = display[: self.MAX_RESULT_DISPLAY] + "\n... [结果已截断]"

        # 重新构建卡片内容
        lines = [f"[bold]工具:[/bold] {self.tool_name}"]
        if self._args:
            lines.append("[bold]参数:[/bold]")
            for k, v in self._args.items():
                lines.append(f"  {k} = {v!r}")
        lines.append("")
        lines.append(f"[bold]结果:[/bold]")
        lines.append(display)

        try:
            body = self.query_one(f"#card-body-{self.card_id}", Static)
            body.update("\n".join(lines))
        except Exception:
            pass  # widget 可能尚未挂载

        # 更新标题添加完成标记
        self.set_title(f"✅ {self.title.lstrip('🔧 ')}")
