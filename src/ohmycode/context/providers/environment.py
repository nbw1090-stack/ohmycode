"""环境上下文提供者 — 注入运行时环境信息。

收集以下信息注入系统提示词：
  - 操作系统（platform / uname）
  - 当前工作目录
  - Git 仓库状态（分支、远程、最近提交）
  - 当前使用的模型名称
  - 当前日期时间
"""

import os
import platform
import subprocess
from datetime import datetime
from pathlib import Path

from ohmycode.context.parts import ContextSnippet, SystemPromptPart
from ohmycode.context.protocols import ContextProvider


def _get_os_info() -> str:
    """获取操作系统信息。"""
    return f"{platform.system()} {platform.release()} ({platform.machine()})"


def _get_cwd() -> str:
    """获取当前工作目录。"""
    return os.getcwd()


def _get_git_info() -> str:
    """获取 Git 仓库信息。

    返回格式化的多行文本，包含分支、远程仓库和最近提交。
    如果不在 Git 仓库中，返回提示信息。
    """
    lines: list[str] = []

    def _git(*args: str) -> str | None:
        try:
            result = subprocess.run(
                ["git", *args],
                capture_output=True,
                text=True,
                timeout=5,
            )
            return result.stdout.strip() if result.returncode == 0 else None
        except (FileNotFoundError, subprocess.TimeoutExpired):
            return None

    branch = _git("rev-parse", "--abbrev-ref", "HEAD")
    if branch is None:
        return "不在 Git 仓库中"

    lines.append(f"分支: {branch}")

    remote = _git("remote", "get-url", "origin")
    if remote:
        lines.append(f"远程: {remote}")

    # 最近 3 条提交（简短格式）
    log = _git("log", "--oneline", "-3")
    if log:
        lines.append("最近提交:")
        for line in log.splitlines():
            lines.append(f"  {line}")

    # 工作区状态
    status = _git("status", "--porcelain")
    if status:
        changed = len(status.splitlines())
        lines.append(f"工作区: {changed} 个未提交变更")
    else:
        lines.append("工作区: 干净")

    return "\n".join(lines)


def _build_environment_section(
    model_name: str,
) -> str:
    """构建环境信息段落。"""
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    lines = [
        "# 环境",
        f"- 操作系统: {_get_os_info()}",
        f"- 工作目录: {_get_cwd()}",
        f"- 模型: {model_name}",
        f"- 当前时间: {now}",
        "",
        "## Git 状态",
        _get_git_info(),
    ]
    return "\n".join(lines)


class EnvironmentContextProvider:
    """提供运行时环境信息作为系统提示词的一部分。

    在 IdentityContextProvider（priority=10..40）之后、
    ToolDocsContextProvider（priority=50）之前插入，
    priority=45。

    Args:
        model_name: 当前使用的 LLM 模型名称
    """

    def __init__(self, model_name: str = "unknown") -> None:
        self._model_name = model_name

    def system_prompt_parts(self) -> list[SystemPromptPart]:
        return [
            SystemPromptPart(
                name="environment",
                content=_build_environment_section(self._model_name),
                priority=45,
            )
        ]

    def context_snippets(self) -> list[ContextSnippet]:
        return []
