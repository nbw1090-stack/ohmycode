"""Session 管理模块——Agent 的会话与上下文生命周期。

核心组件：
- Session: 唯一真相源，包含所有对话状态
- SessionStore: JSONL 持久化 + 多工作区隔离
- UsageTracker: Token 用量追踪，支持跨重启恢复
- compact_session: 上下文压缩（七段式摘要 + 边界安全）
- SummaryCompressionBudget: 摘要预算驱动的行级选择器

设计参考：claw-code 第06章（会话管理）+ 第07章（上下文压缩）。
"""

from ohmycode.session.compactor import (
    CompactionConfig,
    CompactionResult,
    compact_session,
    maybe_auto_compact,
    should_compact,
    summarize_messages,
)
from ohmycode.session.models import (
    PromptEntry,
    Session,
    SessionCompaction,
    SessionFork,
    TokenUsage,
)
from ohmycode.session.store import SessionStore, workspace_fingerprint
from ohmycode.session.summary_budget import SummaryCompressionBudget, compress_summary
from ohmycode.session.usage import UsageTracker

__all__ = [
    # Models
    "Session",
    "SessionCompaction",
    "SessionFork",
    "TokenUsage",
    "PromptEntry",
    # Store
    "SessionStore",
    "workspace_fingerprint",
    # Compactor
    "CompactionConfig",
    "CompactionResult",
    "compact_session",
    "should_compact",
    "summarize_messages",
    "maybe_auto_compact",
    # Summary Budget
    "SummaryCompressionBudget",
    "compress_summary",
    # Usage
    "UsageTracker",
]
