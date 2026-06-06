"""上下文装配的数据类型。"""

from dataclasses import dataclass, field


@dataclass(frozen=True)
class SystemPromptPart:
    """系统提示词的一个段落，由 ContextProvider 贡献。

    Attributes:
        name: 段落唯一标识（用于去重）
        content: 段落文本内容
        priority: 排序优先级，数值越小越靠前
    """
    name: str
    content: str
    priority: int = 100


@dataclass(frozen=True)
class ContextSnippet:
    """额外的上下文片段（如文件内容、环境信息等）。

    Attributes:
        name: 片段唯一标识
        content: 片段文本内容
        metadata: 附带的元数据
    """
    name: str
    content: str
    metadata: dict = field(default_factory=dict)
