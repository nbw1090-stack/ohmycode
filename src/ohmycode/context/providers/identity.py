"""Agent 身份上下文提供者 — 贡献 Agent 的角色定义。"""

from ohmycode.context.parts import ContextSnippet, SystemPromptPart
from ohmycode.context.protocols import ContextProvider


class IdentityContextProvider:
    """提供 Agent 的身份和基本行为描述。

    这是最低优先级（priority=10）的上下文提供者，
    确保身份信息出现在系统提示词的最前面。
    """

    def system_prompt_parts(self) -> list[SystemPromptPart]:
        return [
            SystemPromptPart(
                name="identity",
                content=(
                    "你是 ohmycode，一个模块化的编程助手。\n"
                    "你通过调用工具来帮助用户完成编程任务。\n"
                    "在执行操作前，请先说明你打算做什么。\n"
                    "使用中文与用户交流。"
                ),
                priority=10,
            )
        ]

    def context_snippets(self) -> list[ContextSnippet]:
        return []
