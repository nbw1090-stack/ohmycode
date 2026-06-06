"""工具文档上下文提供者 — 将可用工具的文档注入系统提示词。"""

from langchain_core.tools import BaseTool

from ohmycode.context.parts import ContextSnippet, SystemPromptPart
from ohmycode.context.protocols import ContextProvider


class ToolDocsContextProvider:
    """将已注册工具的名称和描述注入系统提示词。

    让 Agent 了解自己可以使用哪些工具及其用法。
    """

    def __init__(self, tools: list[BaseTool]) -> None:
        self._tools = tools

    def system_prompt_parts(self) -> list[SystemPromptPart]:
        tool_docs = "\n".join(
            f"- {tool.name}: {tool.description}" for tool in self._tools
        )
        return [
            SystemPromptPart(
                name="tool_docs",
                content=f"你可以使用以下工具：\n{tool_docs}",
                priority=50,
            )
        ]

    def context_snippets(self) -> list[ContextSnippet]:
        return []
