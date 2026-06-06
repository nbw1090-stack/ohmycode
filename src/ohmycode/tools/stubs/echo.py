"""Echo 桩工具 — 返回用户输入的文本。用于验证工具系统。"""

from langchain_core.tools import tool


@tool
def echo(text: str) -> str:
    """将输入文本原样返回。用于测试工具系统是否正常工作。

    Args:
        text: 要回显的文本

    Returns:
        原样返回的输入文本
    """
    return text
