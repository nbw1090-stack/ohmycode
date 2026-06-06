"""上下文装配引擎。

从多个 ContextProvider 收集系统提示词段落，按 priority 排序后拼接为完整系统提示词。
"""

from ohmycode.context.parts import SystemPromptPart
from ohmycode.context.protocols import ContextProvider


def assemble_system_prompt(providers: list[ContextProvider]) -> str:
    """从所有 ContextProvider 收集系统提示词段落，组装为完整的系统提示词。

    处理逻辑：
    1. 从每个 provider 收集 SystemPromptPart
    2. 按 name 去重（后注册的覆盖先注册的）
    3. 按 priority 升序排序
    4. 用双换行拼接为完整文本

    Args:
        providers: 上下文提供者列表

    Returns:
        拼接后的完整系统提示词
    """
    seen: dict[str, SystemPromptPart] = {}
    for provider in providers:
        for part in provider.system_prompt_parts():
            seen[part.name] = part

    sorted_parts = sorted(seen.values(), key=lambda p: p.priority)
    return "\n\n".join(p.content for p in sorted_parts)


def collect_context_snippets(providers: list[ContextProvider]) -> dict[str, str]:
    """从所有 ContextProvider 收集上下文片段。

    Args:
        providers: 上下文提供者列表

    Returns:
        以 name 为 key 的上下文片段字典
    """
    snippets: dict[str, str] = {}
    for provider in providers:
        for snippet in provider.context_snippets():
            snippets[snippet.name] = snippet.content
    return snippets
