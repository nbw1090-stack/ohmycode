"""读取文件桩工具 — 模拟文件读取。用于验证工具系统。"""

from langchain_core.tools import tool


@tool
def read_file(path: str) -> str:
    """读取指定路径文件的内容。

    Args:
        path: 要读取的文件路径

    Returns:
        文件内容的字符串
    """
    # 桩实现：实际读取文件
    import os
    if not os.path.exists(path):
        return f"错误：文件 '{path}' 不存在"
    if os.path.isdir(path):
        return f"错误：'{path}' 是一个目录，不是文件"
    try:
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    except Exception as e:
        return f"读取文件失败：{e}"
