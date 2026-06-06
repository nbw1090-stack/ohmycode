"""LLM 提供者模块。

通过 Protocol 抽象 LLM 后端，支持切换不同的提供商。
当前实现：OpenAI (langchain-openai)。
"""

from ohmycode.llm.openai_provider import OpenAILLMProvider

__all__ = ["OpenAILLMProvider"]
