"""LLM 提供者协议定义。"""

from typing import Protocol, runtime_checkable

from langchain_core.language_models import BaseChatModel


@runtime_checkable
class LLMProvider(Protocol):
    """LLM 提供者协议。

    任何模块都可以实现此协议来提供不同的 LLM 后端。
    目前只有 OpenAI 实现，但未来可以扩展到其他提供商。
    """

    def chat_model(self) -> BaseChatModel:
        """返回配置好的 LangChain ChatModel 实例。"""
        ...
