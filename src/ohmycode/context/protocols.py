"""上下文提供者协议定义。"""

from typing import Protocol, runtime_checkable

from ohmycode.context.parts import ContextSnippet, SystemPromptPart


@runtime_checkable
class ContextProvider(Protocol):
    """上下文提供者协议。

    任何模块都可以实现此协议来向 Agent 贡献上下文。
    系统提示词段落会按 priority 排序后拼接为完整的系统提示词。
    """

    def system_prompt_parts(self) -> list[SystemPromptPart]:
        """返回要拼入系统提示词的段落列表。"""
        ...

    def context_snippets(self) -> list[ContextSnippet]:
        """返回额外的上下文片段。"""
        ...
