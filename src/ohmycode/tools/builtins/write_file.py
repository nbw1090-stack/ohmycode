"""写入文件工具 — 将内容写入指定文件。"""

from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from ohmycode.tools.base import PermissionResult, ToolDefinition, ValidationResult


class WriteFileInput(BaseModel):
    """write_file 工具的输入参数。"""

    path: str = Field(description="要写入的文件路径（相对于工作目录）")
    content: str = Field(description="要写入的文件内容")
    create_dirs: bool = Field(
        default=False, description="如果父目录不存在，是否自动创建"
    )
    encoding: str = Field(default="utf-8", description="文件编码")
    append: bool = Field(default=False, description="是否追加模式（默认覆盖）")


class WriteFileDef(ToolDefinition):
    """将内容写入指定文件。

    安全属性：
        - 只读：否
        - 破坏性：是（覆盖已有文件）
        - 并发安全：否
    """

    name = "write_file"
    aliases = ["file_write", "create_file"]
    max_result_size = 10_000

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
            "将内容写入指定文件。如果文件已存在，默认覆盖原有内容。"
            "可以通过 append=True 追加到文件末尾。"
            "支持自动创建父目录。"
        )

    def prompt_description(self) -> str:
        return (
            "当你需要创建或修改文件时使用此工具。写入代码文件、配置文件等。"
            "注意：默认会覆盖已有文件内容，请谨慎使用。"
        )

    def input_schema(self) -> type[BaseModel]:
        return WriteFileInput

    def validate_input(self, input_data: BaseModel) -> ValidationResult:
        data = input_data  # type: WriteFileInput
        errors = []

        if not data.path.strip():
            errors.append("文件路径不能为空")

        if data.content is None:
            errors.append("文件内容不能为 None")

        return ValidationResult(is_valid=len(errors) == 0, errors=errors)

    def check_permissions(self, input_data: BaseModel) -> PermissionResult:
        data = input_data  # type: WriteFileInput
        from ohmycode.tools.builtins._security import validate_path_in_cwd

        return validate_path_in_cwd(data.path, "write_file")

    def execute(self, **kwargs: Any) -> str:
        data = WriteFileInput.model_validate(kwargs)
        path = Path(data.path).resolve()

        # 创建父目录
        if data.create_dirs:
            path.parent.mkdir(parents=True, exist_ok=True)

        if not path.parent.exists():
            return f"错误：父目录 '{path.parent}' 不存在（可设置 create_dirs=True 自动创建）"

        try:
            mode = "a" if data.append else "w"
            existed = path.exists()
            with open(path, mode, encoding=data.encoding) as f:
                f.write(data.content)

            action = "追加到" if data.append else ("覆盖" if existed else "创建")
            line_count = data.content.count("\n") + (1 if data.content and not data.content.endswith("\n") else 0)
            size = len(data.content.encode(data.encoding))

            return (
                f"成功{action}文件 '{data.path}'\n"
                f"  行数: {line_count}\n"
                f"  大小: {size} 字节"
            )

        except PermissionError:
            return f"错误：没有权限写入文件 '{data.path}'"
        except Exception as e:
            return f"写入文件失败：{e}"

    def to_classifier_input(self) -> str:
        return "写入文件 create modify file edit save"
