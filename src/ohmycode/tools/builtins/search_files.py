"""搜索文件工具 — 在文件中搜索文本模式。"""

import os
import re
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from ohmycode.tools.base import PermissionResult, ToolDefinition, ValidationResult


class SearchFilesInput(BaseModel):
    """search_files 工具的输入参数。"""

    pattern: str = Field(description="要搜索的文本模式（支持正则表达式）")
    directory: str = Field(default=".", description="搜索的根目录")
    file_pattern: str = Field(default="*", description="文件名过滤（glob 语法，如 '*.py'）")
    max_results: int = Field(default=50, ge=1, le=500, description="最大返回匹配数")
    case_sensitive: bool = Field(default=True, description="是否区分大小写")


class SearchFilesDef(ToolDefinition):
    """在文件中搜索文本模式。

    安全属性：
        - 只读：是
        - 破坏性：否
        - 并发安全：是
    """

    name = "search_files"
    aliases = ["grep", "search", "find_text"]
    max_result_size = 50_000

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
            "在指定目录的文件中搜索文本模式。支持正则表达式和文件名过滤。"
            "返回匹配的文件路径、行号和匹配行内容。"
        )

    def prompt_description(self) -> str:
        return (
            "当你需要在代码中查找特定的文本、函数定义、变量引用等时使用此工具。"
            "类似 grep 命令的功能。"
        )

    def input_schema(self) -> type[BaseModel]:
        return SearchFilesInput

    def validate_input(self, input_data: BaseModel) -> ValidationResult:
        data = input_data  # type: SearchFilesInput
        errors = []

        if not data.pattern.strip():
            errors.append("搜索模式不能为空")
            return ValidationResult(is_valid=False, errors=errors)

        # 验证正则表达式是否合法
        try:
            flags = 0 if data.case_sensitive else re.IGNORECASE
            re.compile(data.pattern, flags)
        except re.error as e:
            errors.append(f"无效的正则表达式: {e}")

        return ValidationResult(is_valid=len(errors) == 0, errors=errors)

    def check_permissions(self, input_data: BaseModel) -> PermissionResult:
        data = input_data  # type: SearchFilesInput
        from ohmycode.tools.builtins._security import validate_path_in_cwd

        return validate_path_in_cwd(data.directory, "search_files", field_name="directory")

    def execute(self, **kwargs: Any) -> str:
        data = SearchFilesInput.model_validate(kwargs)
        directory = Path(data.directory).resolve()

        if not directory.exists():
            return f"错误：目录 '{data.directory}' 不存在"
        if not directory.is_dir():
            return f"错误：'{data.directory}' 不是一个目录"

        try:
            flags = 0 if data.case_sensitive else re.IGNORECASE
            regex = re.compile(data.pattern, flags)
        except re.error as e:
            return f"错误：无效的正则表达式: {e}"

        # 二进制文件扩展名
        binary_extensions = {
            ".pyc", ".so", ".dll", ".exe", ".bin", ".png", ".jpg",
            ".jpeg", ".gif", ".bmp", ".ico", ".wav", ".mp3", ".mp4",
            ".zip", ".tar", ".gz", ".rar", ".7z", ".pdf", ".o", ".a",
        }

        from fnmatch import fnmatch

        results = []
        total_matches = 0
        files_searched = 0

        for root, _dirs, files in os.walk(directory):
            for filename in sorted(files):
                if not fnmatch(filename, data.file_pattern):
                    continue

                filepath = Path(root) / filename

                # 跳过二进制文件
                if filepath.suffix.lower() in binary_extensions:
                    continue

                # 跳过隐藏文件和常见忽略目录
                if filename.startswith("."):
                    continue

                try:
                    with open(filepath, "r", encoding="utf-8", errors="replace") as f:
                        for line_num, line in enumerate(f, 1):
                            if regex.search(line):
                                rel_path = filepath.relative_to(directory)
                                results.append(
                                    f"{rel_path}:{line_num}: {line.rstrip()}"
                                )
                                total_matches += 1
                                if total_matches >= data.max_results:
                                    break

                    files_searched += 1

                    if total_matches >= data.max_results:
                        break

                except (PermissionError, OSError):
                    continue

            if total_matches >= data.max_results:
                break

        if not results:
            return f"在 '{data.directory}' 中未找到匹配 '{data.pattern}' 的内容（搜索了 {files_searched} 个文件）"

        header = f"搜索 '{data.pattern}' 在 '{data.directory}' 中的结果："
        footer = f"\n共 {total_matches} 个匹配（搜索了 {files_searched} 个文件）"
        if total_matches >= data.max_results:
            footer += f" [已达到最大结果数 {data.max_results}]"

        return header + "\n" + "\n".join(results) + footer

    def to_classifier_input(self) -> str:
        return "搜索文件 grep find text pattern"
