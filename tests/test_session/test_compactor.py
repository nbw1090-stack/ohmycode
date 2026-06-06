"""上下文压缩测试。"""

import pytest
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage

from ohmycode.session.compactor import (
    CompactionConfig,
    compact_session,
    estimate_message_tokens,
    get_compact_continuation_message,
    maybe_auto_compact,
    merge_compact_summaries,
    should_compact,
    summarize_messages,
)
from ohmycode.session.models import Session


def _make_session_with_n_turns(n: int, long_content: bool = False) -> Session:
    """创建包含 N 轮对话的 Session。

    每轮：HumanMessage + AIMessage（+ 可选 ToolMessage）。
    如果 long_content=True，消息内容会很长以触发 token 估算阈值。
    """
    session = Session()
    for i in range(n):
        if long_content:
            text = f"Turn {i}: " + "x" * 2000
        else:
            text = f"Turn {i}: user message"
        session.push_message(HumanMessage(content=text))
        session.push_message(AIMessage(content=f"Turn {i}: assistant reply"))
    return session


def _make_session_with_tool_use() -> Session:
    """创建包含 ToolUse/ToolResult 对的 Session。"""
    session = Session()
    session.push_message(HumanMessage(content="read the file"))
    session.push_message(
        AIMessage(
            content="Let me read it.",
            tool_calls=[{"id": "tc-1", "name": "read_file", "args": {"path": "main.py"}}],
        )
    )
    session.push_message(
        ToolMessage(content="file content", tool_call_id="tc-1", name="read_file")
    )
    session.push_message(AIMessage(content="Here's what I found."))
    session.push_message(HumanMessage(content="fix it"))
    session.push_message(AIMessage(content="Fixed!"))
    session.push_message(HumanMessage(content="run tests"))
    session.push_message(AIMessage(content="All tests passed."))
    return session


class TestEstimateTokens:
    def test_human_message(self):
        msg = HumanMessage(content="hello world")
        tokens = estimate_message_tokens(msg)
        assert tokens > 0

    def test_ai_with_tool_calls(self):
        msg = AIMessage(
            content="thinking",
            tool_calls=[{"id": "tc-1", "name": "bash", "args": {"command": "ls"}}],
        )
        tokens = estimate_message_tokens(msg)
        assert tokens > 0

    def test_longer_message_more_tokens(self):
        short = HumanMessage(content="hi")
        long = HumanMessage(content="x" * 1000)
        assert estimate_message_tokens(long) > estimate_message_tokens(short)


class TestShouldCompact:
    def test_small_session_not_compact(self):
        session = _make_session_with_n_turns(3)
        config = CompactionConfig(preserve_recent_messages=4, max_estimated_tokens=10000)
        assert not should_compact(session, config)

    def test_large_session_should_compact(self):
        session = _make_session_with_n_turns(10, long_content=True)
        config = CompactionConfig(preserve_recent_messages=2, max_estimated_tokens=0)
        assert should_compact(session, config)

    def test_preserve_all_not_compact(self):
        session = _make_session_with_n_turns(3)
        config = CompactionConfig(preserve_recent_messages=10, max_estimated_tokens=0)
        assert not should_compact(session, config)


class TestSummarizeMessages:
    def test_basic_summary(self):
        messages = [
            HumanMessage(content="Fix the bug in main.py"),
            AIMessage(content="I'll read the file."),
            HumanMessage(content="Please run the tests"),
            AIMessage(content="All tests passed."),
        ]
        summary = summarize_messages(messages)

        assert "<summary>" in summary
        assert "</summary>" in summary
        assert "Scope:" in summary
        assert "user=2" in summary
        assert "assistant=2" in summary

    def test_summary_with_tools(self):
        messages = [
            HumanMessage(content="read main.py"),
            AIMessage(
                content="",
                tool_calls=[{"id": "tc-1", "name": "read_file", "args": {"path": "main.py"}}],
            ),
            ToolMessage(content="content", tool_call_id="tc-1", name="read_file"),
        ]
        summary = summarize_messages(messages)

        assert "Tools mentioned: read_file" in summary

    def test_pending_work_detection(self):
        messages = [
            HumanMessage(content="fix the bug"),
            AIMessage(content="Fixed. Next: add regression tests."),
        ]
        summary = summarize_messages(messages)

        assert "Pending work:" in summary
        assert "Next: add regression tests" in summary

    def test_key_files_extraction(self):
        messages = [
            HumanMessage(content="Fix the bug in src/main.py"),
            AIMessage(content="I'll check src/utils.py as well."),
        ]
        summary = summarize_messages(messages)

        assert "Key files referenced:" in summary

    def test_timeline_included(self):
        messages = [
            HumanMessage(content="hello"),
            AIMessage(content="world"),
        ]
        summary = summarize_messages(messages)

        assert "- Key timeline:" in summary
        assert "user: hello" in summary
        assert "assistant: world" in summary


class TestCompactSession:
    def test_no_compact_when_small(self):
        session = _make_session_with_n_turns(2)
        config = CompactionConfig(preserve_recent_messages=4, max_estimated_tokens=10)
        result = compact_session(session, config)

        assert result.removed_message_count == 0
        assert result.compacted_session is session

    def test_compact_removes_messages(self):
        session = _make_session_with_n_turns(10, long_content=True)
        config = CompactionConfig(preserve_recent_messages=2, max_estimated_tokens=0)
        result = compact_session(session, config)

        assert result.removed_message_count > 0
        assert result.compacted_session is not None
        assert len(result.compacted_session.messages) < len(session.messages)

    def test_compact_produces_system_summary(self):
        session = _make_session_with_n_turns(10, long_content=True)
        config = CompactionConfig(preserve_recent_messages=2, max_estimated_tokens=0)
        result = compact_session(session, config)

        # 压缩后的第一条消息应该是 SystemMessage（续接摘要）
        first_msg = result.compacted_session.messages[0]
        assert isinstance(first_msg, SystemMessage)
        assert "continued from a previous conversation" in first_msg.content

    def test_compact_preserves_recent_messages(self):
        session = _make_session_with_n_turns(10, long_content=True)
        config = CompactionConfig(preserve_recent_messages=4, max_estimated_tokens=0)
        result = compact_session(session, config)

        # 保留最近 4 条消息 + 1 条 SystemMessage = 5 条
        assert len(result.compacted_session.messages) == 5

    def test_compact_records_metadata(self):
        session = _make_session_with_n_turns(10, long_content=True)
        config = CompactionConfig(preserve_recent_messages=2, max_estimated_tokens=0)
        result = compact_session(session, config)

        assert result.compacted_session.compaction is not None
        assert result.compacted_session.compaction.count == 1
        assert result.compacted_session.compaction.removed_message_count > 0

    def test_tool_use_tool_result_boundary_safety(self):
        """压缩不应拆散 ToolUse/ToolResult 对。"""
        session = _make_session_with_tool_use()
        config = CompactionConfig(preserve_recent_messages=2, max_estimated_tokens=0)
        result = compact_session(session, config)

        if result.removed_message_count == 0:
            # 消息太少没触发压缩
            return

        messages = result.compacted_session.messages
        # 检查没有孤立的 ToolMessage
        for i, msg in enumerate(messages):
            if isinstance(msg, ToolMessage):
                # 前面应该有包含对应 tool_call 的 AIMessage
                assert i > 0, "ToolMessage should not be the first message"
                found = False
                for j in range(i - 1, -1, -1):
                    prev = messages[j]
                    if isinstance(prev, AIMessage):
                        for tc in getattr(prev, "tool_calls", []):
                            if tc.get("id") == msg.tool_call_id:
                                found = True
                                break
                    if found:
                        break
                assert found, (
                    f"ToolMessage at index {i} has no matching ToolUse"
                )

    def test_double_compaction_merges_summaries(self):
        """多次压缩应合并摘要。"""
        session = _make_session_with_n_turns(20, long_content=True)

        # 第一次压缩
        config = CompactionConfig(preserve_recent_messages=4, max_estimated_tokens=0)
        result1 = compact_session(session, config)
        assert result1.removed_message_count > 0

        # 添加更多消息
        compacted = result1.compacted_session
        for i in range(10):
            compacted.push_message(HumanMessage(content=f"More {i}: " + "y" * 500))
            compacted.push_message(AIMessage(content=f"Reply {i}: " + "z" * 500))

        # 第二次压缩
        result2 = compact_session(compacted, config)
        if result2.removed_message_count > 0:
            # 检查合并后的 SystemMessage 包含 "Previously compacted"
            first_msg = result2.compacted_session.messages[0]
            assert isinstance(first_msg, SystemMessage)
            # 合并后应该有 Previously 或 Newly compacted context
            content = first_msg.content
            assert (
                "Previously compacted context" in content
                or "Newly compacted context" in content
                or "<summary>" in content
            )


class TestMergeCompactSummaries:
    def test_first_compaction(self):
        new = "<summary>\n- Scope: 4 messages.\n</summary>"
        result = merge_compact_summaries(None, new)
        assert result == new

    def test_merge_preserves_both(self):
        old = "<summary>\n- Scope: 6 messages.\n- Key timeline:\n  - user: old\n</summary>"
        new = "<summary>\n- Scope: 4 messages.\n- Key timeline:\n  - user: new\n</summary>"
        result = merge_compact_summaries(old, new)

        assert "Previously compacted context" in result
        assert "Newly compacted context" in result
        # 旧时间线被丢弃，只保留新的
        assert "user: new" in result


class TestGetCompactContinuationMessage:
    def test_basic_message(self):
        msg = get_compact_continuation_message("summary text")
        assert "continued from a previous conversation" in msg
        assert "summary text" in msg

    def test_suppress_follow_up(self):
        msg = get_compact_continuation_message("summary", suppress_follow_up=True)
        assert "Continue the conversation" in msg

    def test_recent_preserved_note(self):
        msg = get_compact_continuation_message("summary", recent_preserved=True)
        assert "Recent messages are preserved verbatim" in msg


class TestMaybeAutoCompact:
    def test_below_threshold_no_compact(self):
        session = _make_session_with_n_turns(10, long_content=True)
        result = maybe_auto_compact(session, cumulative_input_tokens=50, threshold=100_000)
        assert result is None

    def test_above_threshold_compacts(self):
        session = _make_session_with_n_turns(10, long_content=True)
        result = maybe_auto_compact(session, cumulative_input_tokens=150_000, threshold=100_000)
        assert result is not None
        assert result.removed_message_count > 0
