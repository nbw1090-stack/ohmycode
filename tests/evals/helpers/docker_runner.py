"""Docker 隔离运行器 — 安全测试在容器中执行，不影响宿主机。

使用 Docker SDK 管理 container 生命周期。
如果 Docker 不可用，提供 skip 机制。
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent.parent.parent.parent / ".env")

IMAGE_TAG = "ohmycode-eval"


@dataclass
class ContainerResult:
    """容器执行结果。"""

    exit_code: int
    stdout: str
    stderr: str

    @property
    def succeeded(self) -> bool:
        return self.exit_code == 0


def _docker_available() -> bool:
    """检查 Docker daemon 是否可用。"""
    try:
        import docker
        client = docker.from_env()
        client.ping()
        return True
    except Exception:
        return False


def _get_docker_client():
    """获取 Docker client 实例。"""
    try:
        import docker
        return docker.from_env()
    except Exception as e:
        raise RuntimeError(f"Docker 不可用: {e}") from e


class DockerRunner:
    """管理 Docker 容器，为安全测试提供隔离执行环境。"""

    def __init__(self, image_tag: str = IMAGE_TAG) -> None:
        self.image_tag = image_tag
        self._client = None
        self._containers: list[Any] = []

    @property
    def client(self):
        if self._client is None:
            self._client = _get_docker_client()
        return self._client

    def ensure_image(self) -> None:
        """确保评估镜像存在，不存在则构建。"""
        try:
            self.client.images.get(self.image_tag)
        except Exception:
            self.build_image()

    def build_image(self) -> None:
        """构建评估 Docker 镜像。"""
        project_root = Path(__file__).parent.parent.parent.parent.parent
        dockerfile_path = Path(__file__).parent.parent / "docker" / "Dockerfile.eval"

        self.client.images.build(
            path=str(project_root),
            dockerfile=str(dockerfile_path),
            tag=self.image_tag,
            rm=True,
        )

    def run_python(
        self,
        code: str,
        workspace_files: dict[str, str] | None = None,
        env_vars: dict[str, str] | None = None,
        timeout: int = 60,
    ) -> ContainerResult:
        """在容器中执行 Python 代码。

        Args:
            code: 要执行的 Python 代码
            workspace_files: 挂载到容器 /workspace 的文件 {路径: 内容}
            env_vars: 注入到容器的环境变量
            timeout: 执行超时（秒）

        Returns:
            ContainerResult
        """
        self.ensure_image()

        # 准备环境变量
        container_env: dict[str, str] = {}
        if env_vars:
            container_env.update(env_vars)
        # 注入 LLM API 配置（用于 agent 安全测试）
        for key in ("OPENAI_API_KEY", "OPENAI_MODEL", "OPENAI_BASE_URL", "OPENAI_TEMPERATURE"):
            val = os.environ.get(key)
            if val:
                container_env[key] = val

        # 准备工作区文件
        volumes: dict[str, dict[str, str]] = {}
        tmpdir = None

        if workspace_files:
            tmpdir = tempfile.mkdtemp()
            for rel_path, content in workspace_files.items():
                file_path = Path(tmpdir) / rel_path
                file_path.parent.mkdir(parents=True, exist_ok=True)
                file_path.write_text(content, encoding="utf-8")
            volumes[tmpdir] = {"bind": "/workspace", "mode": "rw"}

        try:
            container = self.client.containers.run(
                image=self.image_tag,
                command=["python", "-c", code],
                environment=container_env,
                volumes=volumes if volumes else None,
                working_dir="/workspace",
                detach=True,
                stdout=True,
                stderr=True,
            )
            self._containers.append(container)

            # 等待执行完成
            result = container.wait(timeout=timeout)

            stdout = container.logs(stdout=True, stderr=False).decode("utf-8", errors="replace")
            stderr = container.logs(stdout=False, stderr=True).decode("utf-8", errors="replace")

            return ContainerResult(
                exit_code=result.get("StatusCode", -1),
                stdout=stdout,
                stderr=stderr,
            )
        except Exception as e:
            return ContainerResult(
                exit_code=-1,
                stdout="",
                stderr=str(e),
            )
        finally:
            if tmpdir:
                import shutil
                shutil.rmtree(tmpdir, ignore_errors=True)

    def run_pytest(
        self,
        test_ids: list[str] | None = None,
        env_vars: dict[str, str] | None = None,
        timeout: int = 120,
    ) -> ContainerResult:
        """在容器中运行 pytest。

        Args:
            test_ids: 指定运行的测试 ID（如 ["tests/evals/test_security.py::TestPathTraversal"]）
            env_vars: 注入的环境变量
            timeout: 执行超时

        Returns:
            ContainerResult
        """
        self.ensure_image()

        container_env: dict[str, str] = {}
        if env_vars:
            container_env.update(env_vars)
        for key in ("OPENAI_API_KEY", "OPENAI_MODEL", "OPENAI_BASE_URL", "OPENAI_TEMPERATURE"):
            val = os.environ.get(key)
            if val:
                container_env[key] = val

        cmd = ["python", "-m", "pytest", "-v", "--tb=short"]
        if test_ids:
            cmd.extend(test_ids)

        try:
            container = self.client.containers.run(
                image=self.image_tag,
                command=cmd,
                environment=container_env,
                working_dir="/app",
                detach=True,
                stdout=True,
                stderr=True,
            )
            self._containers.append(container)

            result = container.wait(timeout=timeout)

            stdout = container.logs(stdout=True, stderr=False).decode("utf-8", errors="replace")
            stderr = container.logs(stdout=False, stderr=True).decode("utf-8", errors="replace")

            return ContainerResult(
                exit_code=result.get("StatusCode", -1),
                stdout=stdout,
                stderr=stderr,
            )
        except Exception as e:
            return ContainerResult(
                exit_code=-1,
                stdout="",
                stderr=str(e),
            )

    def cleanup(self) -> None:
        """清理所有创建的容器。"""
        for container in self._containers:
            try:
                container.remove(force=True)
            except Exception:
                pass
        self._containers.clear()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.cleanup()


# ===== pytest skip 装饰器 =====

def skip_if_no_docker():
    """返回 pytest.skip 如果 Docker 不可用。"""
    if not _docker_available():
        import pytest
        pytest.skip("Docker daemon 不可用，跳过安全测试")


def docker_available() -> bool:
    """检查 Docker 是否可用。"""
    return _docker_available()
