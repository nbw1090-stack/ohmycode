"""评估测试共享 fixtures。

提供工作区、agent graph、judge client、recorder 和 Docker 隔离环境。
"""

from pathlib import Path

import pytest
from dotenv import load_dotenv

# 在测试加载前注入 .env 环境变量
_env_path = Path(__file__).parent.parent.parent / ".env"
load_dotenv(_env_path)

from tests.evals.helpers.recorder import ToolCallRecorder  # noqa: E402


@pytest.fixture
def eval_workspace(tmp_path, monkeypatch):
    """创建预置样本项目的临时工作区，并 chdir 到该目录。"""
    from tests.evals.helpers.workspace import create_sample_project

    workspace = create_sample_project(tmp_path)
    monkeypatch.chdir(workspace)
    return workspace


@pytest.fixture
def eval_graph(eval_workspace):
    """通过真实 Assembler 路径构建 agent graph。

    使用 .env 中的 LLM 配置和所有内置工具。
    遵循与 __main__.py 相同的装配流程。
    """
    from ohmycode.assembler import Assembler
    from ohmycode.config.settings import Settings
    from ohmycode.context.providers.environment import EnvironmentContextProvider
    from ohmycode.context.providers.identity import IdentityContextProvider
    from ohmycode.context.providers.tool_docs import ToolDocsContextProvider
    from ohmycode.llm.openai_provider import OpenAILLMProvider
    from ohmycode.tools.builtins import BuiltinToolProvider

    config_path = Path(__file__).parent.parent.parent / "src" / "ohmycode" / "config" / "defaults.toml"
    settings = Settings.from_toml(config_path)

    # 与 __main__.py 一致：先收集工具，再创建 ToolDocsContextProvider
    llm_provider = OpenAILLMProvider(settings.llm)
    tool_provider = BuiltinToolProvider()
    all_tools = tool_provider.tools()

    assembler = Assembler(
        settings=settings,
        llm_provider=llm_provider,
        context_providers=[
            IdentityContextProvider(),
            EnvironmentContextProvider(model_name=settings.llm.model),
            ToolDocsContextProvider(all_tools),
        ],
        tool_providers=[tool_provider],
    )

    graph = assembler.build()
    yield graph

    # teardown: 重置全局审批 handler
    import ohmycode.tools.base as tool_base
    tool_base.TOOL_APPROVAL_HANDLER = None


@pytest.fixture
def judge_client():
    """实例化 LLMJudgeClient，使用 .env 中的模型配置。"""
    from tests.evals.judge.client import LLMJudgeClient

    return LLMJudgeClient()


@pytest.fixture
def recorder():
    """实例化 ToolCallRecorder。"""
    return ToolCallRecorder()


@pytest.fixture
def docker_isolated():
    """提供 Docker 隔离环境。安全测试在容器中执行。

    如果 Docker 不可用，自动 skip。
    """
    from tests.evals.helpers.docker_runner import DockerRunner, skip_if_no_docker

    skip_if_no_docker()

    runner = DockerRunner()
    yield runner
    runner.cleanup()
