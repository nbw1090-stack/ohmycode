"""内置上下文提供者。"""

from ohmycode.context.providers.identity import IdentityContextProvider
from ohmycode.context.providers.tool_docs import ToolDocsContextProvider

__all__ = ["IdentityContextProvider", "ToolDocsContextProvider"]
