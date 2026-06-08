"""工具调用卡片组件 — 对话流中的可折叠工具调用详情。

以折叠状态内联在对话流中，标题显示工具名和参数摘要。
点击展开后显示完整的调用参数和返回结果。
"""

from textual.widgets import Collapsible, Static

# 工具名 → 关键参数名映射，用于提取折叠标题的摘要参数
_TOOL_KEY_PARAMS: dict[str, str] = {
    "write_file": "path",
    "read_file": "path",
    "create_file": "path",
    "list_directory": "path",
    "search_files": "pattern",
    "execute_command": "command",
}

# 折叠标题中参数值的最大长度
_MAX_TITLE_VALUE_LEN = 60


def _format_collapsed_title(
    tool_name: str, args: dict, indicator: str = "🔧"
) -> str:
    """生成简洁的折叠标题，格式为 '{indicator} {tool_name} {key_value}'。

    优先从 _TOOL_KEY_PARAMS 映射中取关键参数，未命中则取第一个参数。
    超长值截断加 '…'。
    """
    # 1. 尝试从映射中取关键参数
    key = _TOOL_KEY_PARAMS.get(tool_name)
    value = args.get(key) if key else None

    # 2. 未命中则取第一个参数
    if value is None and args:
        value = next(iter(args.values()))

    # 3. 格式化
    if value is None:
        return f"{indicator} {tool_name}"

    value_str = str(value)
    if len(value_str) > _MAX_TITLE_VALUE_LEN:
        value_str = value_str[:_MAX_TITLE_VALUE_LEN] + "…"
    return f"{indicator} {tool_name} {value_str}"


def _format_result_summary(tool_name: str, result_text: str) -> str:
    """生成工具结果的摘要文本，避免在 TUI 中显示大段文件内容。

    - 读文件类工具：显示行数和字符数摘要
    - 写文件类工具：显示写入成功和字符数
    - 命令执行：保留完整输出（通常较短且有意义）
    - 通用 fallback：超长时截断显示摘要
    """
    if not result_text:
        return "(空结果)"

    char_count = len(result_text)
    line_count = result_text.count("\n") + 1

    # 读文件类 — 只显示摘要
    if tool_name in ("read_file",):
        return f"已读取 {line_count} 行 ({char_count} 字符)"

    # 写文件类 — 只显示确认
    if tool_name in ("write_file", "create_file"):
        return f"写入成功 ({char_count} 字符)"

    # 命令执行 — 保留输出，但超长时截断
    if tool_name == "execute_command":
        if char_count > 500:
            truncated = result_text[:500]
            return f"{truncated}\n… (共 {char_count} 字符)"
        return result_text

    # 通用 fallback — 超过 200 字符则截断
    if char_count > 200:
        return f"{result_text[:200]}… (共 {char_count} 字符)"

    return result_text


class ToolCallCard(Collapsible):
    """对话流中的可折叠工具调用卡片。

    默认折叠，只显示一行摘要如 "🔧 write_file src/main.py"。
    展开后显示完整的参数和返回结果摘要。

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

        # 构建简洁标题：工具名 + 关键参数值
        title = _format_collapsed_title(tool_name, args, indicator="🔧")

        super().__init__(title=title, collapsed=True, id=card_id)

    def compose(self):
        """卡片展开后的内容区域。"""
        # 显示工具名和关键参数（不显示完整参数列表）
        lines = [f"[bold]工具:[/bold] {self.tool_name}"]
        if self._args:
            lines.append("[bold]参数:[/bold]")
            for k, v in self._args.items():
                lines.append(f"  {k} = {v!r}")
        lines.append("")  # 留空行等待结果
        yield Static("\n".join(lines), id=f"card-body-{self.card_id}")

    def set_result(self, result_text: str) -> None:
        """设置工具调用的返回结果，更新卡片内容。

        Args:
            result_text: 工具返回的结果文本
        """
        self._result = result_text

        # 生成结果摘要（避免显示大段文件内容）
        display = _format_result_summary(self.tool_name, result_text)

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

        # 更新标题：使用辅助函数保持格式一致，修复 reactive 属性赋值
        self.title = _format_collapsed_title(
            self.tool_name, self._args, indicator="✅"
        )
