"""工具模块。

通过 Protocol 抽象工具提供者，支持任意扩展。
内置桩工具用于验证系统。
"""

from ohmycode.tools.registry import ToolRegistry
from ohmycode.tools.stubs import StubToolProvider

__all__ = ["ToolRegistry", "StubToolProvider"]
