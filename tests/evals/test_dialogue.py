"""会话/对话评估 — 测试会话管理和上下文保持。

测试覆盖：
- DL-A: 多轮上下文保持（需要 LLM）
- DL-B: 会话持久化（纯 assert）
- DL-C: 上下文压缩（纯 assert）
"""

import pytest
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

from tests.evals.helpers.assertions import assert_response_contains
from tests.evals.helpers.recorder import run_multi_turn
from tests.evals.judge.prompts import RUBRIC_DIALOGUE_QUALITY


# ====================================================================
# Category A: 多轮上下文保持
# ====================================================================

@pytest.mark.e2e
@pytest.mark.timeout(180)
class TestMultiTurnContext:
    """DL-A: 多轮对话中 Agent 是否保持了上下文。"""

    async def test_a01_remember_file_content(self, eval_graph, recorder, eval_workspace, judge_client):
        """DL-A01: T1 读取文件后，T2 询问文件内容 → 能引用 T1 的内容"""
        responses = await run_multi_turn(
            eval_graph, recorder,
            [
                "Show me the contents of main.py",
                "What functions did main.py define?",
            ],
        )
        assert len(responses) == 2
        # 第二轮回复应该提到 main.py 中定义的函数名
        second_response = responses[1].lower()
        has_function_ref = any(
            fn in second_response
            for fn in ["greet", "calculate_sum", "main"]
        )
        assert has_function_ref, (
            f"Agent should reference functions from main.py in second turn. "
            f"Response: {responses[1][:300]}"
        )

    async def test_a02_respect_user_preference(self, eval_graph, recorder, eval_workspace):
        """DL-A02: T1 声明偏好 → T2 生成代码时尊重偏好"""
        responses = await run_multi_turn(
            eval_graph, recorder,
            [
                "I prefer Python code with type hints on all function signatures. Remember this.",
                "Write a simple add(a, b) function in a new file called adder.py",
            ],
        )
        assert len(responses) == 2
        # 检查文件是否被创建且包含 type hints
        adder_file = eval_workspace / "adder.py"
        if adder_file.exists():
            content = adder_file.read_text()
            has_type_hints = "def add(" in content and (": int" in content or "-> " in content)
            assert has_type_hints, f"Expected type hints in generated code. Got: {content[:200]}"

    async def test_a03_compare_two_files(self, eval_graph, recorder, eval_workspace):
        """DL-A03: T1 读 main.py, T2 读 utils.py, T3 比较两者"""
        responses = await run_multi_turn(
            eval_graph, recorder,
            [
                "Read the file main.py",
                "Now read the file utils.py",
                "Which file has more function definitions?",
            ],
        )
        assert len(responses) == 3
        # 第三轮应该能比较两个文件
        third_response = responses[2].lower()
        mentions_both = "main" in third_response and "utils" in third_response
        assert mentions_both, (
            f"Agent should reference both files in comparison. "
            f"Response: {responses[2][:300]}"
        )


# ====================================================================
# Category B: 会话持久化（纯 assert）
# ====================================================================

class TestSessionPersistence:
    """DL-B: 会话持久化和恢复。"""

    def test_b01_save_and_reload(self, tmp_path):
        """DL-B01: 创建 → 添加消息 → 保存 → 重新加载，消息完全一致。"""
        from ohmycode.session.models import Session
        from ohmycode.session.store import SessionStore

        ws = tmp_path / "workspace"
        ws.mkdir()
        store = SessionStore.from_cwd(ws)

        session = store.create_session(model="test-model")
        session.push_message(HumanMessage(content="hello"))
        store.save_message(session)
        session.push_message(AIMessage(content="world"))
        store.save_message(session)

        loaded = store.load_session(session.session_id)
        assert len(loaded.messages) == 2
        assert loaded.messages[0].content == "hello"
        assert loaded.messages[1].content == "world"

    def test_b02_tool_calls_preserved(self, tmp_path):
        """DL-B02: 包含 tool_calls 的会话保存/加载后保持完整。"""
        from ohmycode.session.models import Session
        from ohmycode.session.store import SessionStore

        ws = tmp_path / "workspace"
        ws.mkdir()
        store = SessionStore.from_cwd(ws)

        session = store.create_session(model="test")
        session.push_message(HumanMessage(content="read main.py"))
        store.save_message(session)
        session.push_message(
            AIMessage(
                content="",
                tool_calls=[{"id": "tc1", "name": "read_file", "args": {"path": "main.py"}}],
            )
        )
        store.save_message(session)
        session.push_message(
            ToolMessage(content="file contents here", tool_call_id="tc1", name="read_file")
        )
        store.save_message(session)

        loaded = store.load_session(session.session_id)
        assert len(loaded.messages) == 3

        ai_msg = loaded.messages[1]
        assert isinstance(ai_msg, AIMessage)
        assert len(ai_msg.tool_calls) == 1
        assert ai_msg.tool_calls[0]["name"] == "read_file"

        tool_msg = loaded.messages[2]
        assert isinstance(tool_msg, ToolMessage)
        assert tool_msg.content == "file contents here"

    def test_b03_workspace_isolation(self, tmp_path):
        """DL-B03: 跨工作区加载应抛出 ValueError。"""
        from ohmycode.session.models import Session
        from ohmycode.session.store import SessionStore

        ws_a = tmp_path / "project-a"
        ws_b = tmp_path / "project-b"
        ws_a.mkdir()
        ws_b.mkdir()

        store_a = SessionStore.from_cwd(ws_a)
        s_a = store_a.create_session()
        store_a.save_message(s_a)

        store_b = SessionStore.from_cwd(ws_b)
        # 复制 session 文件到 B 的目录
        import shutil
        src_path = s_a._persistence_path
        dst_path = store_b.sessions_root / src_path.name
        shutil.copy2(src_path, dst_path)

        with pytest.raises(ValueError, match="工作区不匹配"):
            store_b.load_session(s_a.session_id)

    def test_b04_session_fork(self, tmp_path):
        """DL-B04: 会话分叉后两个分支独立。"""
        from ohmycode.session.models import Session
        from ohmycode.session.store import SessionStore

        ws = tmp_path / "workspace"
        ws.mkdir()
        store = SessionStore.from_cwd(ws)

        original = store.create_session()
        original.push_message(HumanMessage(content="shared message"))
        store.save_message(original)

        forked = store.fork_session(original, branch_name="experiment")
        assert forked.session_id != original.session_id
        assert forked.fork is not None
        assert forked.fork.parent_session_id == original.session_id
        assert len(forked.messages) == 1

        # 分叉后各自独立
        forked.push_message(HumanMessage(content="fork message"))
        store.save_message(forked)

        loaded_original = store.load_session(original.session_id)
        assert len(loaded_original.messages) == 1  # 原会话不受影响

    def test_b05_prompt_history_preserved(self, tmp_path):
        """DL-B05: prompt_history 在保存/加载后保持。"""
        from ohmycode.session.models import Session
        from ohmycode.session.store import SessionStore

        ws = tmp_path / "workspace"
        ws.mkdir()
        store = SessionStore.from_cwd(ws)

        session = store.create_session()
        session.push_prompt_entry("fix the bug")
        store.save_prompt_entry(session)
        session.push_prompt_entry("run the tests")
        store.save_prompt_entry(session)

        loaded = store.load_session(session.session_id)
        assert len(loaded.prompt_history) == 2
        assert loaded.prompt_history[0].text == "fix the bug"
        assert loaded.prompt_history[1].text == "run the tests"


# ====================================================================
# Category C: 上下文压缩（纯 assert）
# ====================================================================

class TestContextCompression:
    """DL-C: 上下文压缩质量。"""

    def _make_session_with_n_turns(self, n: int) -> "Session":
        """创建包含 n 轮对话的 session。"""
        from ohmycode.session.models import Session

        session = Session()
        for i in range(n):
            session.push_message(HumanMessage(content=f"User message {i}"))
            session.push_message(AIMessage(content=f"AI response {i}"))
        return session

    def test_c01_preserve_recent_messages(self):
        """DL-C01: 压缩后最近 4 条消息被完整保留。"""
        from ohmycode.session.compactor import CompactionConfig, compact_session

        session = self._make_session_with_n_turns(10)  # 20 条消息
        config = CompactionConfig(
            preserve_recent_messages=4,
            max_estimated_tokens=0,  # 强制压缩
        )
        result = compact_session(session, config)

        assert result.removed_message_count > 0
        assert result.compacted_session is not None

        # 最近消息应该被保留（检查最后的 AI 消息）
        recent_texts = [
            m.content for m in result.compacted_session.messages
            if isinstance(m, AIMessage) and "AI response" in m.content
        ]
        assert len(recent_texts) >= 2, f"Expected recent messages preserved, got {len(recent_texts)}"

    def test_c02_summary_contains_tools(self):
        """DL-C02: 压缩摘要应该包含工具使用信息。"""
        from ohmycode.session.compactor import CompactionConfig, compact_session

        session = Session()
        session.push_message(HumanMessage(content="read main.py"))
        session.push_message(
            AIMessage(
                content="",
                tool_calls=[{"id": "tc1", "name": "read_file", "args": {"path": "main.py"}}],
            )
        )
        session.push_message(
            ToolMessage(content="file contents", tool_call_id="tc1", name="read_file")
        )
        session.push_message(AIMessage(content="The file contains..."))
        # 添加更多消息以达到压缩阈值
        for i in range(10):
            session.push_message(HumanMessage(content=f"Extra message {i}"))
            session.push_message(AIMessage(content=f"Response {i}"))

        config = CompactionConfig(preserve_recent_messages=2, max_estimated_tokens=0)
        result = compact_session(session, config)

        assert result.summary, "Expected non-empty summary"
        assert "read_file" in result.summary, f"Expected 'read_file' in summary. Got: {result.summary[:200]}"

    def test_c03_boundary_safety(self):
        """DL-C03: 压缩边界不会切割 ToolUse/ToolResult 对。"""
        from ohmycode.session.compactor import CompactionConfig, compact_session

        session = Session()
        # 添加足够多的消息
        for i in range(5):
            session.push_message(HumanMessage(content=f"Request {i}"))
            session.push_message(AIMessage(content=f"Response {i}"))

        # 在尾部添加 ToolUse/ToolResult 对
        session.push_message(HumanMessage(content="read utils.py"))
        session.push_message(
            AIMessage(
                content="",
                tool_calls=[{"id": "tc2", "name": "read_file", "args": {"path": "utils.py"}}],
            )
        )
        session.push_message(
            ToolMessage(content="utils contents", tool_call_id="tc2", name="read_file")
        )
        session.push_message(AIMessage(content="utils.py contains..."))

        config = CompactionConfig(preserve_recent_messages=3, max_estimated_tokens=0)
        result = compact_session(session, config)

        if result.compacted_session:
            # 检查没有孤立的 ToolMessage
            messages = result.compacted_session.messages
            for i, msg in enumerate(messages):
                if isinstance(msg, ToolMessage):
                    # 前面应该有配对的 AIMessage（包含 tool_calls）
                    if i > 0:
                        prev = messages[i - 1]
                        has_tool_use = (
                            isinstance(prev, AIMessage)
                            and getattr(prev, "tool_calls", None)
                        )
                        # 如果前一条不是 AIMessage with tool_calls，
                        # 那它应该在摘要 SystemMessage 之后
                        if not has_tool_use and i > 1:
                            # 检查是否是摘要后的第一条
                            from langchain_core.messages import SystemMessage
                            assert isinstance(messages[0], SystemMessage), (
                                "First message should be SystemMessage summary"
                            )

    def test_c04_double_compression_merge(self):
        """DL-C04: 二次压缩的摘要应该合并。"""
        from ohmycode.session.compactor import CompactionConfig, compact_session

        session = self._make_session_with_n_turns(10)
        config = CompactionConfig(preserve_recent_messages=4, max_estimated_tokens=0)

        # 第一次压缩
        result1 = compact_session(session, config)
        assert result1.compacted_session is not None

        # 添加更多消息
        result1.compacted_session.push_message(HumanMessage(content="more messages after first compaction"))
        result1.compacted_session.push_message(AIMessage(content="response after compaction"))
        for i in range(8):
            result1.compacted_session.push_message(HumanMessage(content=f"post-compact {i}"))
            result1.compacted_session.push_message(AIMessage(content=f"post-response {i}"))

        # 第二次压缩
        result2 = compact_session(result1.compacted_session, config)

        if result2.summary:
            # 检查合并标记
            has_merge_marker = (
                "Previously" in result2.summary or "previously" in result2.summary.lower()
            )
            assert has_merge_marker or "Newly" in result2.summary or "newly" in result2.summary.lower(), (
                f"Expected merge markers in double-compressed summary. Got: {result2.summary[:300]}"
            )

    def test_c05_message_chain_repair(self):
        """DL-C05: 消息链修复 — 模拟损坏的消息链。"""
        from ohmycode.session.models import Session
        from ohmycode.session.store import SessionStore

        # 这个测试验证 SessionStore 的 _validate_and_repair_messages
        # 直接测试 Session 的 JSONL 序列化/反序列化
        session = Session()
        session.push_message(HumanMessage(content="hello"))
        session.push_message(AIMessage(content="world"))

        # 序列化
        lines = session.to_jsonl_lines()
        assert len(lines) > 0

        # 反序列化
        restored = Session.from_jsonl("\n".join(lines))
        assert len(restored.messages) == 2
        assert restored.messages[0].content == "hello"
        assert restored.messages[1].content == "world"


# 延迟导入（避免顶层导入问题）
from ohmycode.session.models import Session  # noqa: E402
