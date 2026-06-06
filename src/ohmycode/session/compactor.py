"""SessionCompactor——上下文压缩引擎。

四阶段流水线：
1. 检测（何时压缩）：should_compact() 判断 token 是否超限
2. 决策（能否压缩）：两个条件同时满足（消息数 > 保留数 且 token >= 阈值）
3. 执行（如何压缩）：compact_session() 三段切割 + 七段式摘要 + 边界安全
4. 精炼（摘要压缩）：SummaryCompressionBudget 行级优先级选择器

关键设计：
- 摘要生成是纯函数（不调用 LLM），零延迟、零成本、确定性
- ToolUse/ToolResult 边界安全：不切割配对消息
- 支持多次压缩：旧摘要和新摘要通过 merge 合并

设计参考：claw-code 第07章 上下文压缩的完整工程实现。
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from langchain_core.messages import (
    AIMessage,
    BaseMessage,
    HumanMessage,
    SystemMessage,
    ToolMessage,
)

from ohmycode.session.models import Session
from ohmycode.session.summary_budget import SummaryCompressionBudget, compress_summary


# ── 常量 ──

DEFAULT_PRESERVE_RECENT_MESSAGES = 4
DEFAULT_MAX_ESTIMATED_TOKENS = 10_000
DEFAULT_AUTO_COMPACTION_THRESHOLD = 100_000

# 待办关键词
_PENDING_KEYWORDS = ("todo", "next", "pending", "follow up", "remaining")

# 有趣的文件扩展名
_INTERESTING_EXTENSIONS = (
    ".py", ".rs", ".ts", ".tsx", ".js", ".json", ".md",
    ".yaml", ".yml", ".toml", ".cfg", ".ini",
    ".go", ".java", ".c", ".cpp", ".h",
    ".sh", ".bash", ".zsh",
)

# 续接消息模板
COMPACT_CONTINUATION_PREAMBLE = (
    "This session is being continued from a previous conversation "
    "that ran out of context. The summary below covers the earlier "
    "portion of the conversation.\n\n"
)
COMPACT_RECENT_MESSAGES_NOTE = "Recent messages are preserved verbatim."
COMPACT_DIRECT_RESUME_INSTRUCTION = (
    "Continue the conversation from where it left off without asking "
    "the user any further questions. Resume directly — do not acknowledge "
    "the summary, do not recap what was happening, and do not preface "
    "with continuation text."
)

# 摘要内容截断
MAX_BLOCK_SUMMARY_CHARS = 160
MAX_CURRENT_WORK_CHARS = 200
MAX_KEY_FILES = 8
MAX_PENDING_ITEMS = 3
MAX_RECENT_REQUESTS = 3


# ── 配置 ──


@dataclass(frozen=True)
class CompactionConfig:
    """压缩配置。

    Attributes:
        preserve_recent_messages: 保留最近多少条消息（默认 4）
        max_estimated_tokens: 可压缩消息的最低 token 门槛（默认 10000）
    """

    preserve_recent_messages: int = DEFAULT_PRESERVE_RECENT_MESSAGES
    max_estimated_tokens: int = DEFAULT_MAX_ESTIMATED_TOKENS


@dataclass
class CompactionResult:
    """压缩结果。

    Attributes:
        summary: 摘要文本
        formatted_summary: 格式化后的摘要
        compacted_session: 压缩后的新 Session
        removed_message_count: 移除的消息数
    """

    summary: str = ""
    formatted_summary: str = ""
    compacted_session: Session | None = None
    removed_message_count: int = 0


# ── Token 估算 ──


def estimate_message_tokens(message: BaseMessage) -> int:
    """粗略启发式估算消息的 token 数。

    规则：4 字节约等于 1 token。
    对"是否需要压缩"这个决策来说足够精确。
    """
    total = 0

    # 文本内容
    if message.content:
        total += len(str(message.content)) // 4 + 1

    # 工具调用（AIMessage）
    tool_calls = getattr(message, "tool_calls", None)
    if tool_calls:
        for tc in tool_calls:
            total += len(str(tc.get("name", ""))) // 4 + 1
            total += len(str(tc.get("args", {}))) // 4 + 1

    # 工具结果（ToolMessage）
    if isinstance(message, ToolMessage):
        total += len(str(getattr(message, "name", ""))) // 4 + 1

    return total


# ── 边界检测 ──


def _has_tool_result(message: BaseMessage) -> bool:
    """消息是否是 ToolMessage。"""
    return isinstance(message, ToolMessage)


def _has_tool_use(message: BaseMessage) -> bool:
    """消息是否包含 tool_calls。"""
    return isinstance(message, AIMessage) and bool(
        getattr(message, "tool_calls", None)
    )


def _extract_existing_compacted_summary(message: BaseMessage) -> str | None:
    """从 SystemMessage 中提取已有的摘要。"""
    if not isinstance(message, SystemMessage):
        return None
    content = message.content or ""
    if "<summary>" in content and "</summary>" in content:
        start = content.index("<summary>")
        end = content.index("</summary>") + len("</summary>")
        return content[start:end]
    return None


# ── 摘要生成辅助函数 ──


def _first_text_block(message: BaseMessage) -> str | None:
    """提取消息中的第一个文本内容。"""
    content = message.content
    if content and isinstance(content, str) and content.strip():
        return content.strip()
    return None


def _summarize_block(message: BaseMessage) -> str:
    """将一条消息浓缩为一行摘要文本。"""
    parts: list[str] = []

    # 文本内容
    if message.content:
        text = str(message.content)
        parts.append(text)

    # 工具调用
    tool_calls = getattr(message, "tool_calls", None)
    if tool_calls:
        for tc in tool_calls:
            name = tc.get("name", "")
            args = tc.get("args", {})
            parts.append(f"tool_use {name}({args})")

    # 工具结果
    if isinstance(message, ToolMessage):
        name = getattr(message, "name", "unknown")
        content = str(message.content) if message.content else ""
        is_error = getattr(message, "status", "") == "error"
        prefix = "error " if is_error else ""
        parts.append(f"tool_result {name}: {prefix}{content}")

    combined = " | ".join(parts)
    return _truncate(combined, MAX_BLOCK_SUMMARY_CHARS)


def _truncate(text: str, max_chars: int) -> str:
    """截断文本到指定长度。"""
    if len(text) <= max_chars:
        return text
    return text[: max_chars - 1] + "…"


def _collect_recent_role_summaries(
    messages: list[BaseMessage], role_type: type, count: int
) -> list[str]:
    """收集最近 N 条指定角色消息的文本。"""
    results: list[str] = []
    for msg in reversed(messages):
        if isinstance(msg, role_type):
            text = _first_text_block(msg)
            if text:
                results.append(_truncate(text, MAX_BLOCK_SUMMARY_CHARS))
            if len(results) >= count:
                break
    results.reverse()  # 恢复时间顺序
    return results


def _infer_pending_work(messages: list[BaseMessage]) -> list[str]:
    """推断待办工作——通过关键词匹配。"""
    results: list[str] = []
    for msg in reversed(messages):
        text = _first_text_block(msg)
        if not text:
            continue
        lowered = text.lower()
        if any(kw in lowered for kw in _PENDING_KEYWORDS):
            results.append(_truncate(text, MAX_BLOCK_SUMMARY_CHARS))
        if len(results) >= MAX_PENDING_ITEMS:
            break
    results.reverse()
    return results


def _has_interesting_extension(candidate: str) -> bool:
    """检查文件路径是否有有趣的扩展名。"""
    path = Path(candidate)
    ext = path.suffix.lower()
    return ext in _INTERESTING_EXTENSIONS


def _extract_file_candidates(content: str) -> list[str]:
    """从文本中提取文件路径候选。"""
    candidates: list[str] = []
    for token in content.split():
        # 去掉标点
        cleaned = token.strip(",.:;)('\"`")
        if "/" in cleaned and _has_interesting_extension(cleaned):
            candidates.append(cleaned)
    return candidates


def _collect_key_files(messages: list[BaseMessage]) -> list[str]:
    """提取对话中引用的关键文件路径。"""
    seen: set[str] = set()
    results: list[str] = []

    for msg in messages:
        text = _first_text_block(msg)
        if not text:
            continue
        for candidate in _extract_file_candidates(text):
            if candidate not in seen:
                seen.add(candidate)
                results.append(candidate)

    return results[:MAX_KEY_FILES]


def _infer_current_work(messages: list[BaseMessage]) -> str | None:
    """推断当前正在做什么——取最后一条非空文本。"""
    for msg in reversed(messages):
        text = _first_text_block(msg)
        if text:
            return _truncate(text, MAX_CURRENT_WORK_CHARS)
    return None


# ── 七段式摘要生成 ──


def summarize_messages(messages: list[BaseMessage]) -> str:
    """将一组消息提炼为结构化的七段式摘要。

    整个过程是纯函数——不调用 LLM。
    七个字段全部由计数 + 取值 + 关键词匹配 + 截断 + 字符串拼接生成。

    摘要结构：
    <summary>
    Conversation summary:
    - Scope: N earlier messages compacted (user=X, assistant=Y, tool=Z).
    - Tools mentioned: tool1, tool2.
    - Recent user requests: ...
    - Pending work: ...
    - Key files referenced: ...
    - Current work: ...
    - Key timeline: ...
    </summary>
    """
    # 1. 统计各角色消息数
    user_count = sum(1 for m in messages if isinstance(m, HumanMessage))
    assistant_count = sum(1 for m in messages if isinstance(m, AIMessage))
    tool_count = sum(1 for m in messages if isinstance(m, ToolMessage))

    # 2. 提取工具名列表（去重）
    tool_names: set[str] = set()
    for msg in messages:
        if isinstance(msg, AIMessage):
            for tc in getattr(msg, "tool_calls", []) or []:
                name = tc.get("name", "")
                if name:
                    tool_names.add(name)
        if isinstance(msg, ToolMessage):
            name = getattr(msg, "name", "")
            if name:
                tool_names.add(name)
    sorted_tool_names = sorted(tool_names)

    # 3. 构建七段式摘要
    lines: list[str] = [
        "<summary>",
        "Conversation summary:",
        f"- Scope: {len(messages)} earlier messages compacted "
        f"(user={user_count}, assistant={assistant_count}, tool={tool_count}).",
    ]

    if sorted_tool_names:
        lines.append(f"- Tools mentioned: {', '.join(sorted_tool_names)}.")

    # 最近 3 条用户请求
    recent_requests = _collect_recent_role_summaries(
        messages, HumanMessage, MAX_RECENT_REQUESTS
    )
    if recent_requests:
        lines.append("- Recent user requests:")
        for req in recent_requests:
            lines.append(f"  - {req}")

    # 待办工作
    pending = _infer_pending_work(messages)
    if pending:
        lines.append("- Pending work:")
        for item in pending:
            lines.append(f"  - {item}")

    # 关键文件
    key_files = _collect_key_files(messages)
    if key_files:
        lines.append(f"- Key files referenced: {', '.join(key_files)}.")

    # 当前工作
    current_work = _infer_current_work(messages)
    if current_work:
        lines.append(f"- Current work: {current_work}")

    # 时间线
    lines.append("- Key timeline:")
    for msg in messages:
        role = "unknown"
        if isinstance(msg, HumanMessage):
            role = "user"
        elif isinstance(msg, AIMessage):
            role = "assistant"
        elif isinstance(msg, ToolMessage):
            role = "tool"
        elif isinstance(msg, SystemMessage):
            role = "system"
        content = _summarize_block(msg)
        lines.append(f"  - {role}: {content}")

    lines.append("</summary>")
    return "\n".join(lines)


# ── 续接消息 ──


def get_compact_continuation_message(
    summary: str,
    suppress_follow_up: bool = True,
    recent_preserved: bool = True,
) -> str:
    """生成压缩后的续接 System 消息。

    三层指令：
    1. 情境说明："This session is being continued..."
    2. 上下文补充："Recent messages are preserved verbatim."
    3. 行为约束："Resume directly — do not acknowledge the summary..."
    """
    base = COMPACT_CONTINUATION_PREAMBLE + summary

    if recent_preserved:
        base += "\n\n" + COMPACT_RECENT_MESSAGES_NOTE

    if suppress_follow_up:
        base += "\n" + COMPACT_DIRECT_RESUME_INSTRUCTION

    return base


# ── 摘要合并 ──


def _extract_summary_highlights(summary: str) -> list[str]:
    """从摘要中提取高亮信息（非时间线的行）。"""
    lines: list[str] = []
    in_timeline = False
    for line in summary.splitlines():
        stripped = line.strip()
        if stripped.startswith("- Key timeline:"):
            in_timeline = True
            continue
        if in_timeline:
            continue
        if stripped and stripped not in ("<summary>", "</summary>", "Conversation summary:"):
            lines.append(stripped)
    return lines


def _extract_summary_timeline(summary: str) -> list[str]:
    """从摘要中提取时间线部分。"""
    lines: list[str] = []
    in_timeline = False
    for line in summary.splitlines():
        stripped = line.strip()
        if stripped.startswith("- Key timeline:"):
            in_timeline = True
            continue
        if in_timeline and stripped and stripped != "</summary>":
            lines.append(stripped)
    return lines


def merge_compact_summaries(
    existing_summary: str | None, new_summary: str
) -> str:
    """合并旧摘要和新摘要（用于多次压缩）。

    合并策略：
    - 旧摘要的高亮 → "Previously compacted context"
    - 新摘要的高亮 → "Newly compacted context"
    - 新摘要的时间线 → 保留（旧时间线被丢弃，防止膨胀）
    """
    if not existing_summary:
        return new_summary

    previous_highlights = _extract_summary_highlights(existing_summary)
    new_highlights = _extract_summary_highlights(new_summary)
    new_timeline = _extract_summary_timeline(new_summary)

    lines: list[str] = ["<summary>", "Conversation summary:"]

    if previous_highlights:
        lines.append("- Previously compacted context:")
        for hl in previous_highlights:
            lines.append(f"  {hl}")

    if new_highlights:
        lines.append("- Newly compacted context:")
        for hl in new_highlights:
            lines.append(f"  {hl}")

    if new_timeline:
        lines.append("- Key timeline:")
        for tl in new_timeline:
            lines.append(f"  {tl}")

    lines.append("</summary>")
    return "\n".join(lines)


# ── 核心压缩逻辑 ──


def should_compact(session: Session, config: CompactionConfig) -> bool:
    """判断是否应该压缩。

    两个条件必须同时满足：
    1. 可压缩消息数 > 保留数量
    2. 可压缩消息的估算 token >= 阈值
    """
    start = _compacted_summary_prefix_len(session)
    compactable = session.messages[start:]

    if len(compactable) <= config.preserve_recent_messages:
        return False

    estimated_tokens = sum(estimate_message_tokens(m) for m in compactable)
    return estimated_tokens >= config.max_estimated_tokens


def _compacted_summary_prefix_len(session: Session) -> int:
    """计算已有的摘要 System 消息的长度。"""
    if not session.messages:
        return 0
    first = session.messages[0]
    if isinstance(first, SystemMessage) and _extract_existing_compacted_summary(first):
        return 1
    return 0


def compact_session(
    session: Session,
    config: CompactionConfig | None = None,
) -> CompactionResult:
    """执行上下文压缩。

    步骤：
    1. 检查是否满足压缩条件
    2. 提取已有的旧摘要
    3. 计算分割点（三段切割）
    4. 边界安全保护（不切割 ToolUse/ToolResult 对）
    5. 生成七段式摘要
    6. 合并旧摘要（如有）
    7. 构建压缩后的新 Session
    """
    if config is None:
        config = CompactionConfig()

    # Step 0: 不需要压缩？直接返回
    if not should_compact(session, config):
        return CompactionResult(
            compacted_session=session,
        )

    # Step 1: 提取已有的旧摘要
    existing_summary = None
    compacted_prefix_len = 0
    if session.messages:
        existing_summary = _extract_existing_compacted_summary(session.messages[0])
        if existing_summary:
            compacted_prefix_len = 1

    # Step 2: 计算分割点
    raw_keep_from = max(
        0, len(session.messages) - config.preserve_recent_messages
    )

    # Step 3: 边界安全保护——不拆散 ToolUse/ToolResult 对
    keep_from = _fix_boundary(session.messages, raw_keep_from, compacted_prefix_len)

    # Step 4: 三段切割
    removed = session.messages[compacted_prefix_len:keep_from]
    preserved = session.messages[keep_from:]

    if not removed:
        return CompactionResult(compacted_session=session)

    # Step 5: 生成摘要
    new_summary = summarize_messages(removed)

    # Step 6: 合并旧摘要
    merged_summary = merge_compact_summaries(existing_summary, new_summary)

    # Step 6.5: 如果摘要过长，用 budget 压缩
    budget = SummaryCompressionBudget()
    formatted_summary = compress_summary(merged_summary, budget)

    # Step 7: 构建续接 System 消息
    continuation = get_compact_continuation_message(
        formatted_summary,
        suppress_follow_up=True,
        recent_preserved=bool(preserved),
    )

    # Step 8: 将被移除的用户消息迁移到 prompt_history
    from ohmycode.session.models import PromptEntry, _current_time_ms

    migrated_prompts = list(session.prompt_history)  # 保留已有的 prompt_history
    for msg in removed:
        if isinstance(msg, HumanMessage) and msg.content and msg.content.strip():
            migrated_prompts.append(
                PromptEntry(timestamp_ms=_current_time_ms(), text=msg.content.strip())
            )

    # Step 9: 构建压缩后的 session
    compacted_messages: list[BaseMessage] = [
        SystemMessage(content=continuation)
    ]
    compacted_messages.extend(preserved)

    # 克隆 session，替换 messages
    new_session = Session(
        workspace_root=session.workspace_root,
        model=session.model,
    )
    new_session.session_id = session.session_id
    new_session.version = session.version
    new_session.created_at_ms = session.created_at_ms
    new_session.updated_at_ms = session.updated_at_ms
    new_session.messages = compacted_messages
    new_session.fork = session.fork
    new_session.prompt_history = migrated_prompts
    new_session.last_health_check_ms = session.last_health_check_ms
    new_session._persistence_path = session._persistence_path
    new_session.record_compaction(merged_summary, len(removed))

    return CompactionResult(
        summary=merged_summary,
        formatted_summary=formatted_summary,
        compacted_session=new_session,
        removed_message_count=len(removed),
    )


def _fix_boundary(
    messages: list[BaseMessage],
    raw_keep_from: int,
    compacted_prefix_len: int,
) -> int:
    """边界安全修复——确保不拆散 ToolUse/ToolResult 对。

    如果切割点落在 ToolResult 上，往前回退到配对的 ToolUse
    （在 preceding Assistant 消息里），确保它们总是一起保留或一起移除。
    """
    k = raw_keep_from

    while True:
        if k == 0 or k <= compacted_prefix_len:
            break

        first_preserved = messages[k]

        # 如果保留边界上的第一条不是 ToolMessage，安全
        if not _has_tool_result(first_preserved):
            break

        # 是 ToolMessage，检查前一条是否有 ToolUse
        if k > 0 and _has_tool_use(messages[k - 1]):
            # 完整配对——回退一步把 assistant 也保留
            k = max(compacted_prefix_len, k - 1)
            break

        # 前一条没有 ToolUse——孤立的 ToolResult，继续往前找
        k = max(compacted_prefix_len, k - 1)

    return k


# ── 自动压缩检测 ──


def maybe_auto_compact(
    session: Session,
    cumulative_input_tokens: int,
    threshold: int = DEFAULT_AUTO_COMPACTION_THRESHOLD,
) -> CompactionResult | None:
    """自动压缩检测。

    在每次 turn 结束后检查累计 input tokens 是否达到阈值。
    如果达到，执行压缩。

    Args:
        session: 当前会话
        cumulative_input_tokens: 累计 input token 数
        threshold: 自动压缩阈值（默认 100,000）

    Returns:
        CompactionResult 如果执行了压缩，否则 None
    """
    if cumulative_input_tokens < threshold:
        return None

    # 自动压缩模式：max_estimated_tokens=0，意思是只要有可压缩的消息就压缩
    config = CompactionConfig(max_estimated_tokens=0)
    result = compact_session(session, config)

    if result.removed_message_count == 0:
        return None

    return result
