"""UsageTracker——跨重启的 Token 用量统计。

双层累计：
- latest_turn: 最近一次 API 调用的用量（显示"本轮费用"）
- cumulative: 整个会话累计用量（触发自动压缩 + 显示总费用）
- turns: 总 API 调用次数

设计参考：claw-code 第06章 UsageTracker 的 from_session 恢复机制。
"""

from __future__ import annotations

from dataclasses import dataclass, field

from langchain_core.messages import AIMessage

from ohmycode.session.models import Session, TokenUsage


@dataclass
class UsageTracker:
    """Token 用量追踪器。

    准确性直接影响两个关键决策：
    1. 自动压缩何时触发（cumulative.input_tokens >= threshold）
    2. 费用显示是否准确

    跨重启恢复：from_session() 扫描所有带 usage 的消息重建累计值。
    """

    latest_turn: TokenUsage = field(default_factory=TokenUsage)
    cumulative: TokenUsage = field(default_factory=TokenUsage)
    turns: int = 0

    def record(self, usage: TokenUsage) -> None:
        """记录一次 API 调用的用量。"""
        self.latest_turn = usage
        self.cumulative = self.cumulative + usage
        self.turns += 1

    def record_from_metadata(self, metadata: dict | None) -> None:
        """从 AIMessage.usage_metadata 记录用量。

        即使 metadata 为空也记录一次 turn（代表一次 API 调用，
        只是 usage 信息缺失）。
        """
        if not metadata:
            # 仍然计一次 turn，但不累加 token
            self.turns += 1
            return
        usage = TokenUsage(
            input_tokens=metadata.get("input_tokens", 0),
            output_tokens=metadata.get("output_tokens", 0),
            cache_creation_input_tokens=metadata.get(
                "cache_creation_input_tokens", 0
            ),
            cache_read_input_tokens=metadata.get("cache_read_input_tokens", 0),
        )
        self.record(usage)

    @classmethod
    def from_session(cls, session: Session) -> UsageTracker:
        """从 Session 的消息中恢复用量统计。

        遍历所有消息，找到带 usage_metadata 的 AIMessage，
        累加它们的 token 用量。

        为什么需要这个？
        当用户重启 CLI、恢复一个之前的 session 时，UsageTracker 是新的（从零开始）。
        如果不从 session 恢复，cumulative.input_tokens 就会从 0 开始，
        导致自动压缩的触发判断失效。
        """
        tracker = cls()
        for message in session.messages:
            if isinstance(message, AIMessage):
                metadata = getattr(message, "usage_metadata", None)
                if metadata:
                    usage = TokenUsage(
                        input_tokens=metadata.get("input_tokens", 0),
                        output_tokens=metadata.get("output_tokens", 0),
                        cache_creation_input_tokens=metadata.get(
                            "cache_creation_input_tokens", 0
                        ),
                        cache_read_input_tokens=metadata.get(
                            "cache_read_input_tokens", 0
                        ),
                    )
                    tracker.cumulative = tracker.cumulative + usage
                    tracker.turns += 1

        if tracker.turns > 0:
            # latest_turn 设为最后一条有 usage 的消息
            # （在 from_session 上下文中无法精确知道哪条是"最近的"，
            #   所以保持 latest_turn 为空——它只在上层 _run_agent 完成一轮后设置）
            pass

        return tracker

    def reset(self) -> None:
        """重置所有计数器（开始新会话时使用）。"""
        self.latest_turn = TokenUsage()
        self.cumulative = TokenUsage()
        self.turns = 0
