"""OpenAI LLM 提供者。

封装 langchain-openai 的 ChatOpenAI，实现 LLMProvider 协议。
所有配置（API Key、模型名等）从环境变量读取。
"""

from langchain_core.language_models import BaseChatModel
from langchain_core.tools import BaseTool
from langchain_openai import ChatOpenAI

from ohmycode.config.settings import LLMSettings
from ohmycode.llm.protocols import LLMProvider


class OpenAILLMProvider:
    """OpenAI LLM 提供者。

    实现 LLMProvider 协议，返回配置好的 ChatOpenAI 实例。
    所有配置通过 LLMSettings 从环境变量获取。

    Args:
        settings: LLM 配置（从环境变量读取）
    """

    def __init__(self, settings: LLMSettings) -> None:
        self._settings = settings

    def chat_model(self, tools: list[BaseTool] | None = None) -> BaseChatModel:
        """返回配置好的 ChatOpenAI 实例。

        如果提供了 tools，会自动绑定到模型上，使其具备工具调用能力。

        Args:
            tools: 可选的工具列表，绑定到 LLM

        Returns:
            配置好的 ChatModel 实例

        Raises:
            EnvironmentError: 如果 OPENAI_API_KEY 未设置
        """
        api_key = self._settings.api_key
        if not api_key:
            raise EnvironmentError(
                "环境变量 OPENAI_API_KEY 未设置。"
                "请在 .env 文件中配置 API Key 后重试。"
            )

        kwargs = {
            "model": self._settings.model,
            "temperature": self._settings.temperature,
            "api_key": api_key,
        }

        base_url = self._settings.base_url
        if base_url:
            kwargs["base_url"] = base_url

        model = ChatOpenAI(**kwargs)

        if tools:
            model = model.bind_tools(tools)

        return model
