"""列出文件桩工具 — 列出目录中的文件。用于验证工具系统。"""

from langchain_core.tools import tool


@tool
def list_files(directory: str = ".") -> str:
    """列出指定目录中的文件和子目录。

    Args:
        directory: 要列出的目录路径，默认为当前目录

    Returns:
        目录内容的格式化字符串
    """
    import os
    if not os.path.exists(directory):
        return f"错误：目录 '{directory}' 不存在"
    if not os.path.isdir(directory):
        return f"错误：'{directory}' 不是一个目录"
    try:
        entries = sorted(os.listdir(directory))
        if not entries:
            return f"目录 '{directory}' 为空"
        lines = [f"目录 '{directory}' 的内容："]
        for entry in entries:
            full_path = os.path.join(directory, entry)
            if os.path.isdir(full_path):
                lines.append(f"  📁 {entry}/")
            else:
                lines.append(f"  📄 {entry}")
        return "\n".join(lines)
    except Exception as e:
        return f"列出目录失败：{e}"
