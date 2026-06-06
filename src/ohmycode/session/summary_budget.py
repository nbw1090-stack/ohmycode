"""SummaryCompressionBudget——预算驱动的行级选择器。

当摘要太长时，按四级优先级在预算内保留最重要的行：
- Priority 0: 核心信息（Scope, Current work, Key files 等）
- Priority 1: 章节标题（Key timeline:, Recent user requests: 等）
- Priority 2: 列表项（以 "- " 或 "  - " 开头的行）
- Priority 3: 其他内容

默认预算：1200 字符 / 24 行 / 每行 160 字符。

设计参考：claw-code 第07章 SummaryCompressionBudget 四级优先级选择器。
"""

from __future__ import annotations

import re
from dataclasses import dataclass


# ── 常量 ──

DEFAULT_MAX_CHARS = 1200
DEFAULT_MAX_LINES = 24
DEFAULT_MAX_LINE_CHARS = 160

# 核心细节行的前缀
_CORE_DETAIL_PREFIXES = (
    "- Scope:",
    "- Current work:",
    "- Pending work:",
    "- Key files referenced:",
    "- Tools mentioned:",
    "- Recent user requests:",
    "- Previously compacted context:",
    "- Newly compacted context:",
)

# 章节标题的标记
_SECTION_HEADERS = (
    "Summary:",
    "Conversation summary:",
    "<summary>",
    "</summary>",
    "- Key timeline:",
    "- Recent user requests:",
    "- Pending work:",
    "- Previously compacted context:",
    "- Newly compacted context:",
)


@dataclass(frozen=True)
class SummaryCompressionBudget:
    """摘要压缩预算。

    Attributes:
        max_chars: 摘要总字符数上限
        max_lines: 摘要行数上限
        max_line_chars: 单行字符数上限
    """

    max_chars: int = DEFAULT_MAX_CHARS
    max_lines: int = DEFAULT_MAX_LINES
    max_line_chars: int = DEFAULT_MAX_LINE_CHARS


def _line_priority(line: str) -> int:
    """计算行的优先级（0=最高, 3=最低）。"""
    stripped = line.strip()

    # Priority 0: 核心信息
    if stripped in ("Summary:", "Conversation summary:", "<summary>", "</summary>"):
        return 0
    if any(stripped.startswith(prefix) for prefix in _CORE_DETAIL_PREFIXES):
        return 0

    # Priority 1: 章节标题
    if any(stripped.startswith(h) for h in _SECTION_HEADERS):
        return 1

    # Priority 2: 列表项
    if stripped.startswith("- ") or stripped.startswith("  - "):
        return 2

    # Priority 3: 其他
    return 3


def _truncate_line(line: str, max_chars: int) -> str:
    """截断过长的行。"""
    if len(line) <= max_chars:
        return line
    return line[: max_chars - 1] + "…"


def _collapse_whitespace(text: str) -> str:
    """折叠多余空白。"""
    return re.sub(r"\s+", " ", text).strip()


def _dedupe_key(line: str) -> str:
    """生成去重键（大小写不敏感）。"""
    return _collapse_whitespace(line).lower()


def _normalize_lines(
    summary: str, max_line_chars: int
) -> tuple[list[str], int]:
    """规范化摘要文本：折叠空白、截断长行、去重。

    Returns:
        (normalized_lines, duplicate_count)
    """
    seen: set[str] = set()
    lines: list[str] = []
    duplicate_count = 0

    for raw_line in summary.splitlines():
        collapsed = _collapse_whitespace(raw_line)
        if not collapsed:
            continue

        truncated = _truncate_line(collapsed, max_line_chars)
        key = _dedupe_key(truncated)

        if key in seen:
            duplicate_count += 1
            continue
        seen.add(key)
        lines.append(truncated)

    return lines, duplicate_count


def _select_line_indexes(
    lines: list[str], budget: SummaryCompressionBudget
) -> list[int]:
    """按优先级贪心选择行，在预算内保留最重要的。"""
    selected: set[int] = set()

    for priority in range(4):
        for idx, line in enumerate(lines):
            if idx in selected:
                continue
            if _line_priority(line) != priority:
                continue

            # 试探：加入这一行后，是否还满足预算？
            candidate_lines = [lines[i] for i in sorted(selected | {idx})]
            if len(candidate_lines) > budget.max_lines:
                continue
            total_chars = sum(len(l) for l in candidate_lines)
            if total_chars > budget.max_chars:
                continue

            selected.add(idx)

    return sorted(selected)


def compress_summary(
    summary: str, budget: SummaryCompressionBudget | None = None
) -> str:
    """压缩摘要到预算范围内。

    步骤：
    1. 规范化（折叠空白、截断、去重）
    2. 按优先级选择行
    3. 如有省略，添加省略提示
    """
    if budget is None:
        budget = SummaryCompressionBudget()

    lines, duplicate_count = _normalize_lines(summary, budget.max_line_chars)

    if not lines:
        return ""

    # 选择最重要的行
    selected_indexes = _select_line_indexes(lines, budget)
    selected_lines = [lines[i] for i in selected_indexes]

    # 计算省略行数
    omitted = len(lines) - len(selected_lines)

    if omitted > 0:
        selected_lines.append(f"- … {omitted} additional line(s) omitted.")

    return "\n".join(selected_lines)
