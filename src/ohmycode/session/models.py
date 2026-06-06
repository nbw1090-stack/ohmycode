"""Session 数据模型——Agent 的唯一真相源。

三层字段分类：
- 核心对话数据：messages, compaction, prompt_history
- 身份与定位：session_id, version, workspace_root, model
- 运维与持久化：created_at_ms, updated_at_ms, fork, persistence_path

设计参考：claw-code 第06章 Session 的 12 字段三层分类。
"""

from __future__ import annotations

import time
import uuid
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


def _current_time_ms() -> int:
    """返回当前时间的毫秒时间戳。"""
    return int(time.time() * 1000)


def _generate_session_id() -> str:
    """生成全局唯一的 session ID。

    格式: session-{millis}-{uuid_short}
    使用时间戳 + UUID 短码保证唯一性。
    """
    millis = _current_time_ms()
    short_id = uuid.uuid4().hex[:8]
    return f"session-{millis}-{short_id}"


@dataclass
class SessionCompaction:
    """压缩元数据——记录最近一次压缩的信息。

    Attributes:
        count: 被压缩了多少次
        removed_message_count: 最近一次移除了多少条消息
        summary: 最新的摘要文本
    """

    count: int = 0
    removed_message_count: int = 0
    summary: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "count": self.count,
            "removed_message_count": self.removed_message_count,
            "summary": self.summary,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> SessionCompaction:
        return cls(
            count=data.get("count", 0),
            removed_message_count=data.get("removed_message_count", 0),
            summary=data.get("summary", ""),
        )


@dataclass
class SessionFork:
    """分叉来源信息。

    Attributes:
        parent_session_id: 父会话 ID
        branch_name: 分支名称（可选）
    """

    parent_session_id: str = ""
    branch_name: str | None = None

    def to_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {"parent_session_id": self.parent_session_id}
        if self.branch_name:
            result["branch_name"] = self.branch_name
        return result

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> SessionFork:
        return cls(
            parent_session_id=data.get("parent_session_id", ""),
            branch_name=data.get("branch_name"),
        )


@dataclass
class PromptEntry:
    """用户输入历史条目。

    Attributes:
        timestamp_ms: 时间戳
        text: 用户输入文本
    """

    timestamp_ms: int = 0
    text: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {"timestamp_ms": self.timestamp_ms, "text": self.text}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> PromptEntry:
        return cls(
            timestamp_ms=data.get("timestamp_ms", 0),
            text=data.get("text", ""),
        )


@dataclass
class TokenUsage:
    """四维 Token 用量。

    四个维度直接对应 LLM API 的计费字段：
    - input_tokens: 发给模型的 token
    - output_tokens: 模型生成的 token
    - cache_creation_input_tokens: 写入缓存的 token
    - cache_read_input_tokens: 从缓存读取的 token
    """

    input_tokens: int = 0
    output_tokens: int = 0
    cache_creation_input_tokens: int = 0
    cache_read_input_tokens: int = 0

    @property
    def total_tokens(self) -> int:
        return (
            self.input_tokens
            + self.output_tokens
            + self.cache_creation_input_tokens
            + self.cache_read_input_tokens
        )

    def __add__(self, other: TokenUsage) -> TokenUsage:
        return TokenUsage(
            input_tokens=self.input_tokens + other.input_tokens,
            output_tokens=self.output_tokens + other.output_tokens,
            cache_creation_input_tokens=self.cache_creation_input_tokens
            + other.cache_creation_input_tokens,
            cache_read_input_tokens=self.cache_read_input_tokens
            + other.cache_read_input_tokens,
        )


def _serialize_message(message: BaseMessage) -> dict[str, Any]:
    """将 LangChain 消息序列化为可 JSON 化的字典。"""
    role_map: dict[type, str] = {
        HumanMessage: "user",
        AIMessage: "assistant",
        ToolMessage: "tool",
        SystemMessage: "system",
    }
    role = "unknown"
    for msg_cls, role_name in role_map.items():
        if isinstance(message, msg_cls):
            role = role_name
            break

    blocks: list[dict[str, Any]] = []

    # 文本内容
    if message.content:
        blocks.append({"type": "text", "text": message.content})

    # 工具调用（AIMessage）
    tool_calls = getattr(message, "tool_calls", None)
    if tool_calls:
        for tc in tool_calls:
            blocks.append(
                {
                    "type": "tool_use",
                    "id": tc.get("id", ""),
                    "name": tc.get("name", ""),
                    "input": tc.get("args", {}),
                }
            )

    # 工具结果（ToolMessage）
    if isinstance(message, ToolMessage):
        # ToolMessage 的 content 是工具输出
        # 替换第一个 block 或添加
        tool_result_block = {
            "type": "tool_result",
            "tool_use_id": getattr(message, "tool_call_id", ""),
            "tool_name": getattr(message, "name", ""),
            "output": message.content if isinstance(message.content, str) else str(message.content),
            "is_error": getattr(message, "status", "") == "error",
        }
        blocks = [tool_result_block]  # ToolMessage 用 tool_result block 表示

    result: dict[str, Any] = {"role": role, "blocks": blocks}

    # Usage 元数据（仅 assistant 消息有）
    usage_metadata = getattr(message, "usage_metadata", None)
    if usage_metadata:
        result["usage"] = {
            "input_tokens": usage_metadata.get("input_tokens", 0),
            "output_tokens": usage_metadata.get("output_tokens", 0),
            "cache_creation_input_tokens": usage_metadata.get(
                "cache_creation_input_tokens", 0
            ),
            "cache_read_input_tokens": usage_metadata.get(
                "cache_read_input_tokens", 0
            ),
        }

    # 额外 ID（tool_call_id）
    tool_call_id = getattr(message, "tool_call_id", None)
    if tool_call_id:
        result["tool_call_id"] = tool_call_id

    return result


def _deserialize_message(data: dict[str, Any]) -> BaseMessage:
    """从字典反序列化为 LangChain 消息对象。"""
    role = data.get("role", "unknown")
    blocks = data.get("blocks", [])

    # 提取文本内容
    text_parts: list[str] = []
    tool_calls: list[dict[str, Any]] = []
    tool_use_blocks: list[dict[str, Any]] = []

    for block in blocks:
        block_type = block.get("type", "")
        if block_type == "text":
            text_parts.append(block.get("text", ""))
        elif block_type == "tool_use":
            tool_calls.append(
                {
                    "id": block.get("id", ""),
                    "name": block.get("name", ""),
                    "args": block.get("input", {}),
                }
            )
            tool_use_blocks.append(block)
        elif block_type == "tool_result":
            # ToolMessage
            return ToolMessage(
                content=block.get("output", ""),
                tool_call_id=block.get("tool_use_id", ""),
                name=block.get("tool_name", ""),
                status="error" if block.get("is_error") else "success",
            )

    content = " ".join(text_parts) if text_parts else ""
    usage_data = data.get("usage")

    if role == "user":
        return HumanMessage(content=content)
    elif role == "system":
        return SystemMessage(content=content)
    elif role == "assistant":
        msg = AIMessage(content=content, tool_calls=tool_calls if tool_calls else [])
        if usage_data:
            msg.usage_metadata = {
                "input_tokens": usage_data.get("input_tokens", 0),
                "output_tokens": usage_data.get("output_tokens", 0),
                "cache_creation_input_tokens": usage_data.get(
                    "cache_creation_input_tokens", 0
                ),
                "cache_read_input_tokens": usage_data.get(
                    "cache_read_input_tokens", 0
                ),
            }
        return msg
    elif role == "tool":
        tool_call_id = data.get("tool_call_id", "")
        # 如果没被 tool_result block 处理，fallback
        return ToolMessage(content=content, tool_call_id=tool_call_id)
    else:
        return HumanMessage(content=content)


class Session:
    """Agent 会话——唯一真相源。

    所有 Agent 状态都在 session.messages 里。没有隐式变量、没有全局状态。
    messages 是可调试、可恢复、可重放的。

    三层字段：
    - 核心对话数据：messages, compaction, prompt_history
    - 身份与定位：session_id, version, workspace_root, model
    - 运维基础设施：created_at_ms, updated_at_ms, fork, _persistence_path
    """

    VERSION = 1

    def __init__(
        self,
        session_id: str | None = None,
        workspace_root: Path | str | None = None,
        model: str | None = None,
    ) -> None:
        now = _current_time_ms()
        self.version: int = self.VERSION
        self.session_id: str = session_id or _generate_session_id()
        self.created_at_ms: int = now
        self.updated_at_ms: int = now
        self.messages: list[BaseMessage] = []
        self.compaction: SessionCompaction | None = None
        self.fork: SessionFork | None = None
        self.workspace_root: Path | None = (
            Path(workspace_root) if workspace_root else None
        )
        self.prompt_history: list[PromptEntry] = []
        self.last_health_check_ms: int | None = None
        self.model: str | None = model
        self._persistence_path: Path | None = None

    def _touch(self) -> None:
        """更新 updated_at_ms 时间戳。"""
        self.updated_at_ms = _current_time_ms()

    # ── Builder 方法 ──

    def with_workspace_root(self, root: Path | str) -> Session:
        self.workspace_root = Path(root)
        return self

    def with_persistence_path(self, path: Path | str) -> Session:
        self._persistence_path = Path(path)
        return self

    def with_model(self, model_name: str) -> Session:
        self.model = model_name
        return self

    # ── 消息操作 ──

    def push_message(self, message: BaseMessage) -> None:
        """追加一条消息到会话。

        乐观更新模式：先加到内存，然后尝试持久化。失败则回滚。
        """
        self._touch()
        self.messages.append(message)

    def push_prompt_entry(self, text: str) -> None:
        """追加用户输入到 prompt_history。"""
        self._touch()
        self.prompt_history.append(
            PromptEntry(timestamp_ms=_current_time_ms(), text=text)
        )

    # ── 压缩记录 ──

    def record_compaction(self, summary: str, removed_count: int) -> None:
        """记录一次压缩操作。"""
        self._touch()
        count = (self.compaction.count + 1) if self.compaction else 1
        self.compaction = SessionCompaction(
            count=count,
            removed_message_count=removed_count,
            summary=summary,
        )

    # ── 分叉 ──

    def create_fork(self, branch_name: str | None = None) -> Session:
        """创建会话分叉（不可变操作——原会话不受影响）。

        语义与 git branch 一致：
        1. 克隆所有消息和元数据
        2. 生成新的 session_id
        3. 记录血统（parent_session_id + branch_name）
        4. persistence_path 设为 None（由 SessionStore 负责绑定）
        """
        new_session = Session(
            workspace_root=self.workspace_root,
            model=self.model,
        )
        new_session.messages = list(self.messages)  # 浅拷贝（LangChain 消息不可变）
        new_session.compaction = (
            SessionCompaction(
                self.compaction.count,
                self.compaction.removed_message_count,
                self.compaction.summary,
            )
            if self.compaction
            else None
        )
        new_session.prompt_history = list(self.prompt_history)
        new_session.fork = SessionFork(
            parent_session_id=self.session_id,
            branch_name=branch_name,
        )
        new_session.last_health_check_ms = self.last_health_check_ms
        return new_session

    # ── 序列化 ──

    def to_meta_dict(self) -> dict[str, Any]:
        """序列化为 session_meta record（不含消息）。"""
        meta: dict[str, Any] = {
            "type": "session_meta",
            "version": self.version,
            "session_id": self.session_id,
            "created_at_ms": self.created_at_ms,
            "updated_at_ms": self.updated_at_ms,
        }
        if self.workspace_root:
            meta["workspace_root"] = str(self.workspace_root)
        if self.model:
            meta["model"] = self.model
        if self.fork:
            meta["fork"] = self.fork.to_dict()
        if self.compaction:
            meta["compaction"] = self.compaction.to_dict()
        return meta

    def to_jsonl_lines(self) -> list[str]:
        """将完整 session 序列化为 JSONL 行列表（用于全量快照）。"""
        import json

        lines: list[str] = []

        # 1. session_meta
        lines.append(json.dumps(self.to_meta_dict(), ensure_ascii=False))

        # 2. prompt_history
        for entry in self.prompt_history:
            lines.append(
                json.dumps(
                    {"type": "prompt_history", **entry.to_dict()},
                    ensure_ascii=False,
                )
            )

        # 3. messages
        for msg in self.messages:
            record = {"type": "message", "message": _serialize_message(msg)}
            lines.append(json.dumps(record, ensure_ascii=False))

        # 4. compaction record
        if self.compaction:
            lines.append(
                json.dumps(
                    {
                        "type": "compaction",
                        **self.compaction.to_dict(),
                    },
                    ensure_ascii=False,
                )
            )

        return lines

    @classmethod
    def from_jsonl(cls, content: str) -> Session:
        """从 JSONL 文本反序列化 Session。"""
        import json

        session = cls()
        messages: list[BaseMessage] = []

        for line in content.strip().splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                continue

            record_type = record.get("type", "")

            if record_type == "session_meta":
                session.version = record.get("version", cls.VERSION)
                session.session_id = record.get("session_id", _generate_session_id())
                session.created_at_ms = record.get("created_at_ms", 0)
                session.updated_at_ms = record.get("updated_at_ms", 0)
                ws = record.get("workspace_root")
                if ws:
                    session.workspace_root = Path(ws)
                session.model = record.get("model")
                fork_data = record.get("fork")
                if fork_data:
                    session.fork = SessionFork.from_dict(fork_data)
                compaction_data = record.get("compaction")
                if compaction_data:
                    session.compaction = SessionCompaction.from_dict(compaction_data)

            elif record_type == "message":
                msg_data = record.get("message", {})
                messages.append(_deserialize_message(msg_data))

            elif record_type == "prompt_history":
                session.prompt_history.append(PromptEntry.from_dict(record))

            elif record_type == "compaction":
                session.compaction = SessionCompaction.from_dict(record)

        session.messages = messages
        return session

    def __repr__(self) -> str:
        return (
            f"Session(id={self.session_id!r}, "
            f"messages={len(self.messages)}, "
            f"compactions={self.compaction.count if self.compaction else 0})"
        )
