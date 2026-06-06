"""执行命令工具 — 执行 shell 命令。"""

import subprocess
from typing import Any

from pydantic import BaseModel, Field

from ohmycode.tools.base import PermissionResult, ToolDefinition, ValidationResult


# 危险命令黑名单
DANGEROUS_COMMANDS = [
    "rm -rf /",
    "rm -rf /*",
    "mkfs",
    "dd if=",
    ":(){ :|:& };:",
    "> /dev/sda",
    "chmod -R 777 /",
    "chown -R",
    "wget.*|.*sh",
    "curl.*|.*sh",
]


class ExecuteCommandInput(BaseModel):
    """execute_command 工具的输入参数。"""

    command: str = Field(description="要执行的 shell 命令")
    cwd: str = Field(default="", description="执行命令的工作目录（默认为当前目录）")
    timeout: int = Field(default=30, ge=1, le=300, description="命令超时时间（秒）")


class ExecuteCommandDef(ToolDefinition):
    """执行 shell 命令并返回输出。

    安全属性：
        - 只读：否
        - 破坏性：是
        - 并发安全：否
    """

    name = "execute_command"
    aliases = ["run", "shell", "cmd", "exec"]
    max_result_size = 50_000

    @property
    def is_enabled(self) -> bool:
        return True

    @property
    def is_concurrency_safe(self) -> bool:
        return False

    @property
    def is_read_only(self) -> bool:
        return False

    @property
    def is_destructive(self) -> bool:
        return True

    def description(self) -> str:
        return (
            "执行 shell 命令并返回标准输出和标准错误。"
            "支持设置工作目录和超时时间。命令在子进程中运行，不会阻塞主进程。"
        )

    def prompt_description(self) -> str:
        return (
            "当你需要运行 shell 命令时使用此工具，如编译代码、运行测试、安装依赖等。"
            "命令有超时保护（默认 30 秒），危险命令会被拦截。"
        )

    def input_schema(self) -> type[BaseModel]:
        return ExecuteCommandInput

    def validate_input(self, input_data: BaseModel) -> ValidationResult:
        data = input_data  # type: ExecuteCommandInput
        errors = []

        if not data.command.strip():
            errors.append("命令不能为空")

        return ValidationResult(is_valid=len(errors) == 0, errors=errors)

    def check_permissions(self, input_data: BaseModel) -> PermissionResult:
        data = input_data  # type: ExecuteCommandInput
        command_lower = data.command.lower().strip()

        # 检查危险命令黑名单
        for dangerous in DANGEROUS_COMMANDS:
            if dangerous in command_lower:
                return PermissionResult(
                    behavior="deny",
                    reason=f"命令包含危险操作: '{dangerous}'",
                )

        # 检查写入敏感目录
        sensitive_paths = ["/etc", "/sys", "/proc", "/boot", "/root"]
        for path in sensitive_paths:
            if path in command_lower and ("write" in command_lower or ">" in data.command):
                return PermissionResult(
                    behavior="deny",
                    reason=f"拒绝写入系统敏感目录: {path}",
                )

        return PermissionResult()

    def execute(self, **kwargs: Any) -> str:
        data = ExecuteCommandInput.model_validate(kwargs)
        cwd = data.cwd or None

        try:
            result = subprocess.run(
                data.command,
                shell=True,
                capture_output=True,
                text=True,
                timeout=data.timeout,
                cwd=cwd,
            )

            parts = []
            if result.stdout:
                parts.append(result.stdout.rstrip())
            if result.stderr:
                parts.append(f"[stderr]\n{result.stderr.rstrip()}")

            output = "\n".join(parts) if parts else "(无输出)"

            if result.returncode != 0:
                output += f"\n[退出码: {result.returncode}]"

            return output

        except subprocess.TimeoutExpired:
            return f"错误：命令执行超时（{data.timeout} 秒）"
        except FileNotFoundError:
            return f"错误：找不到命令或工作目录不存在"
        except PermissionError:
            return f"错误：没有权限执行该命令"
        except Exception as e:
            return f"执行命令失败：{e}"

    def to_classifier_input(self) -> str:
        return "执行命令 shell bash run command terminal"
