"""工具安全辅助函数 — 路径验证等共享安全逻辑。"""

import os
from pathlib import Path

from ohmycode.tools.base import PermissionResult


def validate_path_in_cwd(
    path_str: str, tool_name: str, *, field_name: str = "path"
) -> PermissionResult:
    """验证路径是否在当前工作目录内，防止路径遍历攻击。

    Args:
        path_str: 用户提供的路径字符串
        tool_name: 调用此检查的工具名称（用于错误消息）

    Returns:
        PermissionResult: allow 或 deny
    """
    if not path_str.strip():
        return PermissionResult(
            behavior="deny",
            reason="路径不能为空",
        )

    try:
        cwd = Path.cwd().resolve()
        target = (cwd / path_str).resolve()

        # 检查解析后的路径是否在工作目录内
        try:
            target.relative_to(cwd)
        except ValueError:
            return PermissionResult(
                behavior="deny",
                reason=f"{tool_name}: 路径 '{path_str}' 超出工作目录 '{cwd}' 的范围",
            )

        # 返回规范化后的路径供工具使用
        return PermissionResult(
            behavior="allow",
            updated_input={field_name: str(target)},
        )

    except Exception as e:
        return PermissionResult(
            behavior="deny",
            reason=f"{tool_name}: 路径验证失败: {e}",
        )
