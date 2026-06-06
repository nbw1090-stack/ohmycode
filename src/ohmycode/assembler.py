"""Assembler — 组合根。

负责在启动时将所有模块装配在一起：
1. 从各 ContextProvider 收集并组装系统提示词
2. 从各 ToolProvider 收集并注册工具
3. 通过 LLMProvider 创建 ChatModel
4. 调用 build_react_graph() 构建编译后的 Agent 图

这是整个应用的组装点（Composition Root），所有模块通过此处的依赖注入连接。
"""

from dataclasses import dataclass, field

from langchain_core.language_models import BaseChatModel
from langchain_core.tools import BaseTool

from ohmycode.agent.graph import build_react_graph
from ohmycode.config.settings import Settings
from ohmycode.context.assembler import assemble_system_prompt
from ohmycode.context.protocols import ContextProvider
from ohmycode.llm.protocols import LLMProvider
from ohmycode.tools.protocols import ToolProvider


@dataclass
class Assembler:
    """组合根：将所有模块装配为可运行的 Agent。

    Attributes:
        settings: 应用配置
        llm_provider: LLM 提供者
        context_providers: 上下文提供者列表
        tool_providers: 工具提供者列表
    """

    settings: Settings
    llm_provider: LLMProvider
    context_providers: list[ContextProvider] = field(default_factory=list)
    tool_providers: list[ToolProvider] = field(default_factory=list)

    def collect_tools(self) -> list[BaseTool]:
        """从所有 ToolProvider 收集工具。"""
        all_tools: list[BaseTool] = []
        for provider in self.tool_providers:
            all_tools.extend(provider.tools())
        return all_tools

    def collect_system_prompt(self) -> str:
        """从所有 ContextProvider 收集并组装系统提示词。"""
        return assemble_system_prompt(self.context_providers)

    def build(self):
        """装配所有模块，构建并返回编译后的 Agent 图。

        步骤：
        1. 收集工具列表
        2. 通过 LLM Provider 创建 ChatModel（绑定工具）
        3. 组装系统提示词
        4. 构建 ReAct Agent 图

        Returns:
            编译后的 LangGraph 图，支持 .invoke() 和 .astream()
        """
        tools = self.collect_tools()
        model = self.llm_provider.chat_model(tools=tools)
        system_prompt = self.collect_system_prompt()
        return build_react_graph(model, tools, system_prompt)
