"""SessionStore——JSONL 持久化 + 多工作区隔离。

核心机制：
1. workspace fingerprint: FNV-1a 哈希将工作区路径映射为 16 字符十六进制
2. JSONL 追加写入: 每条消息一行，不重写整个文件
3. 原子写入: temp + rename，崩溃安全
4. 日志轮转: 256KB 阈值，最多保留 3 个历史文件
5. 引用别名: latest/last/recent → 最近更新的 session

磁盘布局:
  ~/project/.ohmycode/sessions/{fingerprint}/
  ├── session-{ts}-{id}.jsonl
  ├── session-{ts}-{id}.rot-{ts}.jsonl
  └── ...

设计参考：claw-code 第06章 SessionStore + JSONL 持久化。
"""

from __future__ import annotations

import json
import os
import re
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

from ohmycode.session.models import Session


# ── 常量 ──

ROTATE_AFTER_BYTES = 256 * 1024  # 256KB
MAX_ROTATED_FILES = 3
SESSIONS_DIR_NAME = ".ohmycode"
SESSIONS_SUBDIR = "sessions"

LATEST_ALIASES = frozenset({"latest", "last", "recent"})


# ── FNV-1a Workspace Fingerprint ──


def workspace_fingerprint(workspace_root: Path | str) -> str:
    """用 FNV-1a 哈希将工作区路径映射为 16 字符十六进制。

    FNV-1a 特性：确定性、分布均匀、速度快。
    保证：同一路径同一指纹、不同路径不同指纹。
    """
    input_str = str(workspace_root)
    # FNV-1a 64-bit parameters
    hash_val = 0xCBF29CE484222325
    fnv_prime = 0x100000001B3
    for byte in input_str.encode("utf-8"):
        hash_val ^= byte
        hash_val = (hash_val * fnv_prime) & 0xFFFFFFFFFFFFFFFF
    return f"{hash_val:016x}"


# ── Managed Session Summary ──


@dataclass
class ManagedSessionSummary:
    """已管理的 Session 摘要信息。"""

    id: str
    path: Path
    updated_at_ms: int
    message_count: int
    parent_session_id: str | None = None
    branch_name: str | None = None


# ── Session Store ──


class SessionStore:
    """Session 持久化管理器。

    职责：
    - JSONL 格式的追加写入和全量快照
    - 多工作区隔离（通过 workspace fingerprint）
    - Session 引用解析（别名、路径、ID）
    - 日志轮转和清理
    """

    def __init__(self, sessions_root: Path, workspace_root: Path) -> None:
        self.sessions_root = sessions_root
        self.workspace_root = workspace_root

    @classmethod
    def from_cwd(cls, cwd: Path | str) -> SessionStore:
        """从当前工作目录创建 SessionStore。

        自动创建 .ohmycode/sessions/{fingerprint}/ 目录。
        """
        cwd = Path(cwd).resolve()
        fingerprint = workspace_fingerprint(cwd)
        sessions_root = (
            cwd / SESSIONS_DIR_NAME / SESSIONS_SUBDIR / fingerprint
        )
        sessions_root.mkdir(parents=True, exist_ok=True)
        return cls(sessions_root=sessions_root, workspace_root=cwd)

    # ── Session 生命周期 ──

    def create_session(
        self,
        model: str | None = None,
    ) -> Session:
        """创建新 Session 并绑定持久化路径。"""
        session = Session(
            workspace_root=self.workspace_root,
            model=model,
        )
        path = self._session_path(session.session_id)
        session.with_persistence_path(path)
        self._save_full(session)
        return session

    def save_message(self, session: Session) -> None:
        """追加一条消息到 JSONL 文件（增量写入）。

        如果文件不存在或为空，执行全量快照。
        """
        path = session._persistence_path
        if not path:
            return

        if not path.exists() or path.stat().st_size == 0:
            self._save_full(session)
            return

        # 追加最后一条消息
        if not session.messages:
            return

        from ohmycode.session.models import _serialize_message

        last_msg = session.messages[-1]
        record = {"type": "message", "message": _serialize_message(last_msg)}
        line = json.dumps(record, ensure_ascii=False)

        with open(path, "a", encoding="utf-8") as f:
            f.write(line + "\n")

    def save_prompt_entry(self, session: Session) -> None:
        """追加 prompt_history 条目到 JSONL 文件。"""
        path = session._persistence_path
        if not path or not path.exists():
            return

        if not session.prompt_history:
            return

        last_entry = session.prompt_history[-1]
        record = {"type": "prompt_history", **last_entry.to_dict()}
        line = json.dumps(record, ensure_ascii=False)

        with open(path, "a", encoding="utf-8") as f:
            f.write(line + "\n")

    def save_compaction(self, session: Session) -> None:
        """保存压缩后的完整 Session（全量快照）。"""
        self._save_full(session)

    def _save_full(self, session: Session) -> None:
        """全量快照：将整个 Session 写入 JSONL 文件。

        使用原子写入：先写临时文件，再 rename。
        写入前检查是否需要日志轮转。
        """
        path = session._persistence_path
        if not path:
            return

        # 检查轮转
        if path.exists():
            self._rotate_if_needed(path)

        lines = session.to_jsonl_lines()
        content = "\n".join(lines) + "\n"
        _write_atomic(path, content)

    # ── 加载 ──

    def load_session(self, reference: str) -> Session:
        """根据引用加载 Session。

        引用解析优先级：
        1. 别名（latest/last/recent）
        2. 文件路径（绝对路径或相对路径）
        3. Session ID
        """
        # 1. 别名
        if reference.lower() in LATEST_ALIASES:
            summary = self._latest_session()
            if not summary:
                raise FileNotFoundError("没有找到任何会话")
            path = summary.path
        # 2. 文件路径
        elif Path(reference).exists():
            path = Path(reference).resolve()
        # 3. Session ID
        else:
            path = self._resolve_id(reference)

        return self._load_from_path(path)

    def _load_from_path(self, path: Path) -> Session:
        """从 JSONL 文件加载 Session。"""
        content = path.read_text(encoding="utf-8")
        session = Session.from_jsonl(content)
        session.with_persistence_path(path)

        # 工作区校验
        self._validate_workspace(session, path)

        # 消息链完整性校验与修复
        self._validate_and_repair_messages(session)

        return session

    def _validate_and_repair_messages(self, session: Session) -> None:
        """校验消息链完整性，修复孤立的 tool_calls。

        场景：如果 session 中有 AIMessage(tool_calls) 但没有后续 ToolMessage，
        LLM API 会返回 400 错误。修复方法：截断到第一条孤立消息之前。

        同时也处理连续 HumanMessage 之间没有 AI 回复的情况——这不会导致 API
        错误，但说明之前的 turn 失败了，保留这些消息是安全的。
        """
        messages = session.messages
        i = 0
        cut_at = len(messages)  # 默认不截断

        while i < len(messages):
            msg = messages[i]
            if isinstance(msg, AIMessage) and msg.tool_calls:
                # 检查后续是否有对应的 ToolMessage
                expected_ids = {tc.get("id", "") for tc in msg.tool_calls}
                found_ids: set[str] = set()
                for j in range(i + 1, len(messages)):
                    m = messages[j]
                    if isinstance(m, ToolMessage):
                        tid = getattr(m, "tool_call_id", "")
                        if tid in expected_ids:
                            found_ids.add(tid)
                    # 如果遇到下一条 HumanMessage 或 AIMessage(tool_calls)，
                    # 说明不会再有更多 ToolMessage 了
                    if isinstance(m, HumanMessage):
                        break
                    if isinstance(m, AIMessage) and m.tool_calls:
                        break

                if found_ids != expected_ids:
                    # 找到孤立的 tool_calls，截断到这里
                    cut_at = i
                    break

                # 跳过已匹配的 ToolMessage
                i += 1
                while i < len(messages):
                    if isinstance(messages[i], ToolMessage):
                        i += 1
                    else:
                        break
                continue

            i += 1

        if cut_at < len(messages):
            import logging
            log = logging.getLogger("ohmycode.session")
            log.warning(
                "消息链修复：截断 %d → %d 条消息（移除孤立 tool_calls）",
                len(messages), cut_at,
            )
            session.messages = messages[:cut_at]
            session._touch()

    def _validate_workspace(
        self, session: Session, path: Path
    ) -> None:
        """校验 Session 的工作区是否匹配当前工作区。"""
        if session.workspace_root is None:
            # legacy session without workspace binding
            # 检查文件路径是否在工作区目录内
            try:
                path.relative_to(self.workspace_root)
            except ValueError:
                raise ValueError(
                    f"会话文件不在当前工作区内: {path} "
                    f"(期望: {self.workspace_root})"
                )
            return

        if session.workspace_root.resolve() != self.workspace_root.resolve():
            raise ValueError(
                f"工作区不匹配: 会话属于 {session.workspace_root}，"
                f"当前工作区为 {self.workspace_root}"
            )

    # ── 列表和查找 ──

    def list_sessions(self) -> list[ManagedSessionSummary]:
        """列出当前工作区的所有 Session。"""
        summaries: list[ManagedSessionSummary] = []

        if not self.sessions_root.exists():
            return summaries

        for path in self.sessions_root.glob("session-*.jsonl"):
            # 跳过轮转文件
            if ".rot-" in path.name:
                continue
            try:
                summary = self._summarize_file(path)
                summaries.append(summary)
            except Exception:
                continue

        # 三级排序：语义 updated_at_ms > 文件 mtime > session_id
        # file_mtime 作为后备——当 JSONL 追加写入未更新 session_meta 时
        summaries.sort(
            key=lambda s: (
                s.updated_at_ms,
                int(s.path.stat().st_mtime * 1000) if s.path.exists() else 0,
                s.id,
            ),
            reverse=True,
        )
        return summaries

    def _latest_session(self) -> ManagedSessionSummary | None:
        """获取最近更新的 Session。"""
        sessions = self.list_sessions()
        return sessions[0] if sessions else None

    def _resolve_id(self, session_id: str) -> Path:
        """根据 session_id 查找文件路径。"""
        # 精确匹配
        target = self.sessions_root / f"{session_id}.jsonl"
        if target.exists():
            return target

        # 前缀匹配
        for path in self.sessions_root.glob("session-*.jsonl"):
            if ".rot-" in path.name:
                continue
            if path.stem == session_id or path.stem.startswith(session_id):
                return path

        raise FileNotFoundError(f"找不到会话: {session_id}")

    def _summarize_file(self, path: Path) -> ManagedSessionSummary:
        """从 JSONL 文件中提取摘要信息（不完全加载）。"""
        content = path.read_text(encoding="utf-8")
        session = Session.from_jsonl(content)

        return ManagedSessionSummary(
            id=session.session_id,
            path=path,
            updated_at_ms=session.updated_at_ms,
            message_count=len(session.messages),
            parent_session_id=(
                session.fork.parent_session_id if session.fork else None
            ),
            branch_name=session.fork.branch_name if session.fork else None,
        )

    # ── 分叉 ──

    def fork_session(
        self, session: Session, branch_name: str | None = None
    ) -> Session:
        """分叉会话到新的独立文件。"""
        forked = session.create_fork(branch_name)
        forked.with_workspace_root(self.workspace_root)
        path = self._session_path(forked.session_id)
        forked.with_persistence_path(path)
        self._save_full(forked)
        return forked

    # ── 删除 ──

    def delete_session(self, reference: str) -> None:
        """删除指定 Session 的文件（含轮转文件）。"""
        session = self.load_session(reference)
        path = session._persistence_path
        if path and path.exists():
            path.unlink()
        # 清理轮转文件
        if path:
            stem = path.stem
            for rot in path.parent.glob(f"{stem}.rot-*.jsonl"):
                rot.unlink()

    # ── 内部工具 ──

    def _session_path(self, session_id: str) -> Path:
        return self.sessions_root / f"{session_id}.jsonl"

    def _rotate_if_needed(self, path: Path) -> None:
        """如果文件超过阈值，执行日志轮转。"""
        if not path.exists():
            return
        size = path.stat().st_size
        if size < ROTATE_AFTER_BYTES:
            return

        # 轮转：重命名为 .rot-{timestamp}.jsonl
        import time

        rot_suffix = int(time.time() * 1000)
        rot_path = path.with_name(f"{path.stem}.rot-{rot_suffix}.jsonl")
        path.rename(rot_path)

        # 清理旧轮转文件
        self._cleanup_rotated(path)

    def _cleanup_rotated(self, original_path: Path) -> None:
        """保留最多 MAX_ROTATED_FILES 个轮转文件。"""
        stem = original_path.stem
        rot_files = sorted(
            original_path.parent.glob(f"{stem}.rot-*.jsonl"),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )
        for old_file in rot_files[MAX_ROTATED_FILES:]:
            old_file.unlink()


def _write_atomic(path: Path, content: str) -> None:
    """原子写入：先写临时文件，再 rename。

    在 POSIX 系统上 rename 是原子操作——
    要么完全成功（新文件替换旧文件），要么完全失败（旧文件不受影响）。
    """
    path.parent.mkdir(parents=True, exist_ok=True)

    # 在同一目录创建临时文件（保证同一文件系统，rename 才是原子的）
    fd, tmp_path = tempfile.mkstemp(
        suffix=".tmp",
        prefix=path.stem + "-",
        dir=path.parent,
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(content)
        os.rename(tmp_path, path)
    except BaseException:
        # 清理临时文件
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise
