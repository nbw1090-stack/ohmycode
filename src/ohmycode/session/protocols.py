"""Session 模块的 Protocol 接口定义。

遵循 ohmycode 的 Protocol-based Assembly Pattern：
每个模块通过 Protocol 接口可插拔替换。
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from ohmycode.session.models import Session


@runtime_checkable
class SessionStoreProtocol(Protocol):
    """Session 持久化存储协议。

    实现此协议的类负责 Session 的创建、加载、保存和生命周期管理。
    """

    def create_session(self, model: str | None = None) -> Session:
        """创建新的 Session 并持久化。"""
        ...

    def load_session(self, reference: str) -> Session:
        """根据引用加载 Session（别名/路径/ID）。"""
        ...

    def save_message(self, session: Session) -> None:
        """追加保存最新消息到持久化文件。"""
        ...

    def save_compaction(self, session: Session) -> None:
        """保存压缩后的完整 Session（全量快照）。"""
        ...

    def list_sessions(self) -> list:
        """列出当前工作区的所有 Session。"""
        ...


@runtime_checkable
class CompactorProtocol(Protocol):
    """上下文压缩协议。

    实现此协议的类负责检测和执行上下文压缩。
    """

    def should_compact(self, session: Session) -> bool:
        """判断是否应该压缩。"""
        ...

    def compact(self, session: Session) -> object:
        """执行压缩，返回 CompactionResult。"""
        ...
