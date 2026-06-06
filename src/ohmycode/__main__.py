"""ohmycode 入口模块。

启动流程：
1. 加载 .env 环境变量
2. 加载配置（从 defaults.toml）
3. 创建各模块的 Provider
4. 通过 Assembler 装配所有模块
5. 构建 Agent 图
6. 启动 Textual TUI

用法: python -m ohmycode
"""

import sys
from pathlib import Path

from dotenv import load_dotenv

from ohmycode.assembler import Assembler
from ohmycode.cli.app import OhmycodeApp
from ohmycode.config.settings import Settings
from ohmycode.context.providers.environment import EnvironmentContextProvider
from ohmycode.context.providers.identity import IdentityContextProvider
from ohmycode.context.providers.tool_docs import ToolDocsContextProvider
from ohmycode.llm.openai_provider import OpenAILLMProvider
from ohmycode.tools.builtins import BuiltinToolProvider


def main() -> None:
    """应用主入口函数。"""
    # 1. 加载 .env 文件中的环境变量
    env_path = Path(__file__).parent.parent.parent / ".env"
    load_dotenv(env_path)

    # 2. 加载配置（LLM 配置从环境变量读取，其余从 TOML）
    config_path = Path(__file__).parent / "config" / "defaults.toml"
    settings = Settings.from_toml(config_path)

    # 3. 创建 LLM Provider
    llm_provider = OpenAILLMProvider(settings.llm)

    # 4. 创建工具 Provider
    enabled = settings.tools.enabled or None  # 空列表 → None（启用全部）
    tool_provider = BuiltinToolProvider(enabled=enabled)
    all_tools = tool_provider.tools()

    # 5. 创建上下文 Provider
    context_providers = [
        IdentityContextProvider(),
        EnvironmentContextProvider(model_name=settings.llm.model),
        ToolDocsContextProvider(all_tools),
    ]

    # 6. 通过 Assembler 装配
    assembler = Assembler(
        settings=settings,
        llm_provider=llm_provider,
        context_providers=context_providers,
        tool_providers=[tool_provider],
    )

    try:
        graph = assembler.build()
    except EnvironmentError as e:
        print(f"配置错误: {e}", file=sys.stderr)
        sys.exit(1)

    # 7. 启动 TUI
    app = OhmycodeApp(agent_graph=graph, model_name=settings.llm.model)
    app.run()


if __name__ == "__main__":
    main()
