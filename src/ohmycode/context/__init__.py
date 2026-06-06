"""上下文装配模块。

提供系统提示词和上下文片段的模块化装配能力。
每个 ContextProvider 贡献一部分上下文，由 assembler 统一收集和排序。
"""

from ohmycode.context.assembler import assemble_system_prompt, collect_context_snippets
from ohmycode.context.parts import ContextSnippet, SystemPromptPart
from ohmycode.context.protocols import ContextProvider

__all__ = [
    "assemble_system_prompt",
    "collect_context_snippets",
    "ContextProvider",
    "ContextSnippet",
    "SystemPromptPart",
]
