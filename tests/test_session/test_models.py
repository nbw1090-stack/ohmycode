"""Session 数据模型测试。"""

import json
from pathlib import Path

import pytest
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage

from ohmycode.session.models import (
    PromptEntry,
    Session,
    SessionCompaction,
    SessionFork,
    TokenUsage,
    _deserialize_message,
    _serialize_message,
)


class TestTokenUsage:
    def test_total_tokens(self):
        usage = TokenUsage(
            input_tokens=100,
            output_tokens=50,
            cache_creation_input_tokens=20,
            cache_read_input_tokens=30,
        )
        assert usage.total_tokens == 200

    def test_add(self):
        a = TokenUsage(input_tokens=100, output_tokens=50)
        b = TokenUsage(input_tokens=200, output_tokens=30)
        result = a + b
        assert result.input_tokens == 300
        assert result.output_tokens == 80

    def test_default_zero(self):
        usage = TokenUsage()
        assert usage.total_tokens == 0


class TestSessionCompaction:
    def test_to_dict_and_from_dict(self):
        c = SessionCompaction(count=2, removed_message_count=8, summary="test summary")
        d = c.to_dict()
        restored = SessionCompaction.from_dict(d)
        assert restored.count == 2
        assert restored.removed_message_count == 8
        assert restored.summary == "test summary"

    def test_default_values(self):
        c = SessionCompaction()
        assert c.count == 0
        assert c.summary == ""


class TestSessionFork:
    def test_to_dict_and_from_dict(self):
        f = SessionFork(parent_session_id="session-123", branch_name="bugfix")
        d = f.to_dict()
        restored = SessionFork.from_dict(d)
        assert restored.parent_session_id == "session-123"
        assert restored.branch_name == "bugfix"

    def test_none_branch_name_not_serialized(self):
        f = SessionFork(parent_session_id="session-123")
        d = f.to_dict()
        assert "branch_name" not in d


class TestPromptEntry:
    def test_round_trip(self):
        e = PromptEntry(timestamp_ms=1234567890, text="hello")
        d = e.to_dict()
        restored = PromptEntry.from_dict(d)
        assert restored.timestamp_ms == 1234567890
        assert restored.text == "hello"


class TestMessageSerialization:
    def test_human_message(self):
        msg = HumanMessage(content="hello")
        d = _serialize_message(msg)
        assert d["role"] == "user"
        assert d["blocks"][0]["type"] == "text"
        assert d["blocks"][0]["text"] == "hello"

    def test_ai_message_with_tool_calls(self):
        msg = AIMessage(
            content="Let me read the file.",
            tool_calls=[
                {"id": "tc-1", "name": "read_file", "args": {"path": "test.py"}}
            ],
        )
        d = _serialize_message(msg)
        assert d["role"] == "assistant"
        tool_uses = [b for b in d["blocks"] if b["type"] == "tool_use"]
        assert len(tool_uses) == 1
        assert tool_uses[0]["name"] == "read_file"

    def test_tool_message(self):
        msg = ToolMessage(
            content="file content here",
            tool_call_id="tc-1",
            name="read_file",
        )
        d = _serialize_message(msg)
        assert d["role"] == "tool"
        # ToolMessage 使用 tool_result block
        tool_results = [b for b in d["blocks"] if b["type"] == "tool_result"]
        assert len(tool_results) == 1
        assert tool_results[0]["tool_name"] == "read_file"

    def test_round_trip_human(self):
        original = HumanMessage(content="test message")
        d = _serialize_message(original)
        restored = _deserialize_message(d)
        assert isinstance(restored, HumanMessage)
        assert restored.content == "test message"

    def test_round_trip_ai_with_tools(self):
        original = AIMessage(
            content="thinking...",
            tool_calls=[
                {"id": "tc-1", "name": "bash", "args": {"command": "ls"}}
            ],
        )
        d = _serialize_message(original)
        restored = _deserialize_message(d)
        assert isinstance(restored, AIMessage)
        assert restored.content == "thinking..."
        assert len(restored.tool_calls) == 1
        assert restored.tool_calls[0]["name"] == "bash"

    def test_round_trip_tool_message(self):
        original = ToolMessage(
            content="output",
            tool_call_id="tc-1",
            name="bash",
        )
        d = _serialize_message(original)
        restored = _deserialize_message(d)
        assert isinstance(restored, ToolMessage)
        assert restored.content == "output"


class TestSession:
    def test_create_session(self):
        session = Session()
        assert session.session_id.startswith("session-")
        assert session.version == 1
        assert len(session.messages) == 0
        assert session.compaction is None

    def test_create_with_workspace(self):
        session = Session(workspace_root="/tmp/test")
        assert session.workspace_root == Path("/tmp/test")

    def test_push_message(self):
        session = Session()
        msg = HumanMessage(content="hello")
        session.push_message(msg)
        assert len(session.messages) == 1
        assert session.messages[0].content == "hello"

    def test_push_prompt_entry(self):
        session = Session()
        session.push_prompt_entry("fix the bug")
        assert len(session.prompt_history) == 1
        assert session.prompt_history[0].text == "fix the bug"

    def test_record_compaction(self):
        session = Session()
        session.record_compaction("summary text", 5)
        assert session.compaction is not None
        assert session.compaction.count == 1
        assert session.compaction.removed_message_count == 5
        assert session.compaction.summary == "summary text"

    def test_record_compaction_increments(self):
        session = Session()
        session.record_compaction("first", 3)
        session.record_compaction("second", 2)
        assert session.compaction.count == 2

    def test_fork_immutable(self):
        session = Session(workspace_root="/tmp/test")
        session.push_message(HumanMessage(content="hello"))
        session.push_message(AIMessage(content="world"))

        forked = session.create_fork(branch_name="experiment")

        # forked 有新 ID
        assert forked.session_id != session.session_id

        # forked 有血统信息
        assert forked.fork is not None
        assert forked.fork.parent_session_id == session.session_id
        assert forked.fork.branch_name == "experiment"

        # forked 继承了消息
        assert len(forked.messages) == 2
        assert forked.messages[0].content == "hello"

        # 原会话不受影响
        assert len(session.messages) == 2
        assert session.fork is None

        # forked 没有 persistence_path
        assert forked._persistence_path is None

    def test_fork_inherits_compaction(self):
        session = Session()
        session.record_compaction("summary", 3)
        forked = session.create_fork()
        assert forked.compaction is not None
        assert forked.compaction.count == 1

    def test_jsonl_round_trip(self):
        session = Session(workspace_root="/tmp/test", model="gpt-4o-mini")
        session.push_message(HumanMessage(content="fix the bug"))
        session.push_message(
            AIMessage(
                content="I'll fix it.",
                tool_calls=[
                    {"id": "tc-1", "name": "read_file", "args": {"path": "main.py"}}
                ],
            )
        )
        session.push_message(
            ToolMessage(content="file content", tool_call_id="tc-1", name="read_file")
        )
        session.push_message(AIMessage(content="Fixed!"))
        session.push_prompt_entry("fix the bug")
        session.record_compaction("test summary", 2)

        lines = session.to_jsonl_lines()
        jsonl_text = "\n".join(lines)

        restored = Session.from_jsonl(jsonl_text)

        assert restored.session_id == session.session_id
        assert restored.workspace_root == Path("/tmp/test")
        assert restored.model == "gpt-4o-mini"
        assert len(restored.messages) == 4
        assert isinstance(restored.messages[0], HumanMessage)
        assert isinstance(restored.messages[1], AIMessage)
        assert restored.messages[1].tool_calls[0]["name"] == "read_file"
        assert isinstance(restored.messages[2], ToolMessage)
        assert isinstance(restored.messages[3], AIMessage)
        assert len(restored.prompt_history) == 1
        assert restored.compaction is not None
        assert restored.compaction.count == 1

    def test_meta_dict(self):
        session = Session(workspace_root="/tmp/test", model="test-model")
        meta = session.to_meta_dict()
        assert meta["type"] == "session_meta"
        assert meta["version"] == 1
        assert meta["workspace_root"] == "/tmp/test"
        assert meta["model"] == "test-model"

    def test_touch_updates_timestamp(self):
        session = Session()
        old_ts = session.updated_at_ms
        session._touch()
        assert session.updated_at_ms >= old_ts

    def test_builder_methods(self):
        session = (
            Session()
            .with_workspace_root("/tmp/test")
            .with_persistence_path("/tmp/test/session.jsonl")
            .with_model("gpt-4")
        )
        assert session.workspace_root == Path("/tmp/test")
        assert session._persistence_path == Path("/tmp/test/session.jsonl")
        assert session.model == "gpt-4"
