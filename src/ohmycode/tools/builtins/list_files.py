"""列出文件工具 — 列出目录中的文件和子目录。"""

import os
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from ohmycode.tools.base import PermissionResult, ToolDefinition


class ListFilesInput(BaseModel):
    """list_files 工具的输入参数。"""

    directory: str = Field(default=".", description="要列出的目录路径")
    recursive: bool = Field(default=False, description="是否递归列出子目录")
    pattern: str = Field(default="", description="文件名过滤模式（支持 glob 语法，如 '*.py'）")
    show_hidden: bool = Field(default=False, description="是否显示隐藏文件（以 . 开头）")


class ListFilesDef(ToolDefinition):
    """列出指定目录中的文件和子目录。

    安全属性：
        - 只读：是
        - 破坏性：否
        - 并发安全：是
    """

    name = "list_files"
    aliases = ["ls", "dir", "list_dir"]
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
            "列出指定目录中的文件和子目录。支持递归列出、文件名过滤和隐藏文件显示。"
            "返回格式化的目录树结构。"
        )

    def prompt_description(self) -> str:
        return "当你需要查看项目目录结构、查找文件时使用此工具。"

    def input_schema(self) -> type[BaseModel]:
        return ListFilesInput

    def check_permissions(self, input_data: BaseModel) -> PermissionResult:
        data = input_data  # type: ListFilesInput
        from ohmycode.tools.builtins._security import validate_path_in_cwd

        return validate_path_in_cwd(data.directory, "list_files", field_name="directory")

    def execute(self, **kwargs: Any) -> str:
        data = ListFilesInput.model_validate(kwargs)
        directory = Path(data.directory).resolve()

        if not directory.exists():
            return f"错误：目录 '{data.directory}' 不存在"
        if not directory.is_dir():
            return f"错误：'{data.directory}' 不是一个目录"

        try:
            lines = []
            file_count = 0
            dir_count = 0

            if data.recursive:
                for root, dirs, files in os.walk(directory):
                    # 过滤隐藏目录
                    if not data.show_hidden:
                        dirs[:] = [d for d in dirs if not d.startswith(".")]

                    rel_root = Path(root).relative_to(directory)
                    prefix = "" if str(rel_root) == "." else f"{rel_root}/"

                    entries = sorted(files)
                    if not data.show_hidden:
                        entries = [e for e in entries if not e.startswith(".")]

                    if data.pattern:
                        from fnmatch import fnmatch

                        entries = [e for e in entries if fnmatch(e, data.pattern)]

                    for entry in entries:
                        lines.append(f"  📄 {prefix}{entry}")
                        file_count += 1

                    if not data.pattern:
                        hidden_dirs = sorted(dirs)
                        for d in hidden_dirs:
                            lines.append(f"  📁 {prefix}{d}/")
                            dir_count += 1
            else:
                entries = sorted(os.listdir(directory))
                for entry in entries:
                    if not data.show_hidden and entry.startswith("."):
                        continue

                    full_path = directory / entry
                    if data.pattern and not full_path.is_dir():
                        from fnmatch import fnmatch

                        if not fnmatch(entry, data.pattern):
                            continue

                    if full_path.is_dir():
                        lines.append(f"  📁 {entry}/")
                        dir_count += 1
                    else:
                        lines.append(f"  📄 {entry}")
                        file_count += 1

            if not lines:
                return f"目录 '{data.directory}' 为空"

            header = f"目录 '{data.directory}' 的内容："
            footer = f"\n共 {file_count} 个文件, {dir_count} 个目录"
            return header + "\n" + "\n".join(lines) + footer

        except PermissionError:
            return f"错误：没有权限访问目录 '{data.directory}'"
        except Exception as e:
            return f"列出目录失败：{e}"

    def to_classifier_input(self) -> str:
        return "列出目录文件 ls tree structure"
