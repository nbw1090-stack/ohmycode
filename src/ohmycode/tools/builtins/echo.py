"""Echo 工具 — 原样返回输入文本。用于调试和验证工具系统。"""

from typing import Any

from pydantic import BaseModel, Field

from ohmycode.tools.base import ToolDefinition


class EchoInput(BaseModel):
    """echo 工具的输入参数。"""

    text: str = Field(description="要回显的文本")


class EchoDef(ToolDefinition):
    """将输入文本原样返回。用于测试工具系统是否正常工作。

    安全属性：
        - 只读：是
        - 破坏性：否
        - 并发安全：是
    """

    name = "echo"
    aliases = ["ping"]
    max_result_size = 10_000

    @property
    def is_enabled(self) -> bool:
        return True

    @property
    def is_concurrency_safe(self) -> bool:
        return True

    @property
    def is_read_only(self) -> bool:
        return True

    @property
    def is_destructive(self) -> bool:
        return False

    def description(self) -> str:
        return "将输入文本原样返回。用于测试工具系统是否正常工作。"

    def input_schema(self) -> type[BaseModel]:
        return EchoInput

    def execute(self, **kwargs: Any) -> str:
        data = EchoInput.model_validate(kwargs)
        return data.text
