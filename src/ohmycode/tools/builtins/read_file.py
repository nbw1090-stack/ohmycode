"""读取文件工具 — 读取指定文件的内容。"""

from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from ohmycode.tools.base import PermissionResult, ToolDefinition, ValidationResult


class ReadFileInput(BaseModel):
    """read_file 工具的输入参数。"""

    path: str = Field(description="要读取的文件路径（相对于工作目录）")
    offset: int = Field(default=0, ge=0, description="起始行号（从 0 开始）")
    limit: int = Field(default=2000, ge=1, le=10000, description="最大读取行数")
    encoding: str = Field(default="utf-8", description="文件编码")


class ReadFileDef(ToolDefinition):
    """读取指定路径文件的内容。

    安全属性：
        - 只读：是
        - 破坏性：否
        - 并发安全：是
    """

    name = "read_file"
    aliases = ["cat", "file_read"]
    max_result_size = 100_000

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
        return (
            "读取指定路径文件的内容。支持指定起始行号和最大行数来分段读取大文件。"
            "返回文件内容的字符串，包含行号前缀。"
        )

    def prompt_description(self) -> str:
        return (
            "当你需要查看文件内容时使用此工具。可以读取代码文件、配置文件等。"
            "对于大文件，使用 offset 和 limit 参数分段读取。"
        )

    def input_schema(self) -> type[BaseModel]:
        return ReadFileInput

    def validate_input(self, input_data: BaseModel) -> ValidationResult:
        data = input_data  # type: ReadFileInput
        path = Path(data.path)

        if not data.path.strip():
            return ValidationResult(is_valid=False, errors=["文件路径不能为空"])

        # 检查文件扩展名是否可能是二进制文件
        binary_extensions = {
            ".pyc", ".so", ".dll", ".exe", ".bin", ".png", ".jpg",
            ".jpeg", ".gif", ".bmp", ".ico", ".wav", ".mp3", ".mp4",
            ".zip", ".tar", ".gz", ".rar", ".7z", ".pdf", ".doc",
            ".docx", ".xls", ".xlsx", ".ppt", ".pptx", ".o", ".a",
        }
        if path.suffix.lower() in binary_extensions:
            return ValidationResult(
                is_valid=False,
                errors=[f"文件 '{data.path}' 可能是二进制文件，无法以文本方式读取"],
            )

        return ValidationResult()

    def check_permissions(self, input_data: BaseModel) -> PermissionResult:
        data = input_data  # type: ReadFileInput
        from ohmycode.tools.builtins._security import validate_path_in_cwd

        return validate_path_in_cwd(data.path, "read_file")

    def execute(self, **kwargs: Any) -> str:
        data = ReadFileInput.model_validate(kwargs)
        path = Path(data.path).resolve()

        if not path.exists():
            return f"错误：文件 '{data.path}' 不存在"
        if path.is_dir():
            return f"错误：'{data.path}' 是一个目录，不是文件"

        try:
            with open(path, "r", encoding=data.encoding) as f:
                lines = f.readlines()

            # 应用 offset 和 limit
            selected = lines[data.offset : data.offset + data.limit]

            # 添加行号前缀
            result_lines = []
            for i, line in enumerate(selected, start=data.offset + 1):
                stripped = line.rstrip("\n")
                result_lines.append(f"{i:>6}\t{stripped}")

            total_lines = len(lines)
            shown_lines = len(result_lines)
            header = f"文件: {data.path} (共 {total_lines} 行"
            if shown_lines < total_lines:
                header += f"，显示第 {data.offset + 1}-{data.offset + shown_lines} 行"
            header += ")\n"

            return header + "\n".join(result_lines)

        except UnicodeDecodeError:
            return f"错误：文件 '{data.path}' 编码不匹配（尝试使用 {data.encoding} 编码读取）"
        except PermissionError:
            return f"错误：没有权限读取文件 '{data.path}'"
        except Exception as e:
            return f"读取文件失败：{e}"

    def to_classifier_input(self) -> str:
        return "读取文件内容 view code file"
