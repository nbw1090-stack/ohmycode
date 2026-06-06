"""SessionStore 测试。"""

import json
from pathlib import Path

import pytest
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

from ohmycode.session.store import (
    SessionStore,
    _write_atomic,
    workspace_fingerprint,
)


@pytest.fixture
def tmp_workspace(tmp_path):
    """创建临时工作区目录。"""
    return tmp_path / "workspace"


@pytest.fixture
def store(tmp_workspace):
    """创建基于临时目录的 SessionStore。"""
    tmp_workspace.mkdir(parents=True, exist_ok=True)
    return SessionStore.from_cwd(tmp_workspace)


class TestWorkspaceFingerprint:
    def test_deterministic(self):
        fp1 = workspace_fingerprint("/tmp/project-a")
        fp2 = workspace_fingerprint("/tmp/project-a")
        assert fp1 == fp2

    def test_differs_per_path(self):
        fp_a = workspace_fingerprint("/tmp/project-a")
        fp_b = workspace_fingerprint("/tmp/project-b")
        assert fp_a != fp_b

    def test_format(self):
        fp = workspace_fingerprint("/tmp/test")
        assert len(fp) == 16
        assert all(c in "0123456789abcdef" for c in fp)


class TestSessionStore:
    def test_create_and_load_session(self, store):
        session = store.create_session(model="test-model")
        assert session.session_id.startswith("session-")
        assert session.workspace_root == store.workspace_root

        loaded = store.load_session("latest")
        assert loaded.session_id == session.session_id
        assert len(loaded.messages) == 0

    def test_save_and_load_messages(self, store):
        session = store.create_session()

        # 追加消息
        session.push_message(HumanMessage(content="hello"))
        store.save_message(session)

        session.push_message(AIMessage(content="world"))
        store.save_message(session)

        # 重新加载
        loaded = store.load_session(session.session_id)
        assert len(loaded.messages) == 2
        assert loaded.messages[0].content == "hello"
        assert loaded.messages[1].content == "world"

    def test_latest_alias(self, store):
        import time

        # 创建两个 session，确保时间戳不同
        s1 = store.create_session()
        s1.push_message(HumanMessage(content="first"))
        store.save_message(s1)

        time.sleep(0.01)  # 确保 updated_at_ms 不同

        s2 = store.create_session()
        s2.push_message(HumanMessage(content="second"))
        store.save_message(s2)

        # latest 应该返回 s2（updated_at_ms 更新）
        latest = store.load_session("latest")
        assert latest.session_id == s2.session_id

    def test_list_sessions(self, store):
        s1 = store.create_session()
        s2 = store.create_session()

        sessions = store.list_sessions()
        ids = {s.id for s in sessions}
        assert s1.session_id in ids
        assert s2.session_id in ids

    def test_fork_session(self, store):
        original = store.create_session()
        original.push_message(HumanMessage(content="hello"))
        store.save_message(original)

        forked = store.fork_session(original, branch_name="experiment")
        assert forked.session_id != original.session_id
        assert forked.fork is not None
        assert forked.fork.parent_session_id == original.session_id
        assert forked.fork.branch_name == "experiment"
        assert len(forked.messages) == 1

        # 原会话不受影响
        loaded_original = store.load_session(original.session_id)
        assert loaded_original.fork is None

    def test_delete_session(self, store):
        session = store.create_session()
        session_id = session.session_id

        # 确认存在
        loaded = store.load_session(session_id)
        assert loaded.session_id == session_id

        # 删除
        store.delete_session(session_id)

        # 确认不存在
        with pytest.raises(FileNotFoundError):
            store.load_session(session_id)

    def test_workspace_isolation(self, tmp_path):
        ws_a = tmp_path / "project-a"
        ws_b = tmp_path / "project-b"
        ws_a.mkdir()
        ws_b.mkdir()

        store_a = SessionStore.from_cwd(ws_a)
        store_b = SessionStore.from_cwd(ws_b)

        s_a = store_a.create_session()
        s_a.push_message(HumanMessage(content="message from A"))
        store_a.save_message(s_a)

        # B 的 latest 不应该是 A 的 session
        assert store_b.list_sessions() == []

    def test_workspace_validation(self, tmp_path):
        ws_a = tmp_path / "project-a"
        ws_b = tmp_path / "project-b"
        ws_a.mkdir()
        ws_b.mkdir()

        store_a = SessionStore.from_cwd(ws_a)
        s_a = store_a.create_session()

        store_b = SessionStore.from_cwd(ws_b)

        # 将 A 的 session 文件复制到 B 的目录下（模拟跨工作区加载场景）
        import shutil
        src_path = s_a._persistence_path
        dst_path = store_b.sessions_root / src_path.name
        shutil.copy2(src_path, dst_path)

        with pytest.raises(ValueError, match="工作区不匹配"):
            store_b.load_session(s_a.session_id)

    def test_save_prompt_entry(self, store):
        session = store.create_session()
        session.push_prompt_entry("fix the bug")
        store.save_prompt_entry(session)

        loaded = store.load_session(session.session_id)
        assert len(loaded.prompt_history) == 1
        assert loaded.prompt_history[0].text == "fix the bug"


class TestWriteAtomic:
    def test_creates_file(self, tmp_path):
        path = tmp_path / "test.jsonl"
        _write_atomic(path, "hello\n")
        assert path.read_text() == "hello\n"

    def test_replaces_existing(self, tmp_path):
        path = tmp_path / "test.jsonl"
        _write_atomic(path, "old\n")
        _write_atomic(path, "new\n")
        assert path.read_text() == "new\n"

    def test_creates_parent_dirs(self, tmp_path):
        path = tmp_path / "sub" / "dir" / "test.jsonl"
        _write_atomic(path, "content\n")
        assert path.read_text() == "content\n"
