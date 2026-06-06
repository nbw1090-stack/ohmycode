"""工具定义基类与工厂函数。

提供 ToolDefinition 抽象基类和 build_tool 工厂函数，
用于将工具定义转换为 LangChain StructuredTool 实例。

设计参考：
    - TOOL_DEFAULTS 默认值模式：所有安全属性默认取最保守值
    - buildTool 工厂模式：将定义转换为可执行的工具实例
    - Tool<Input,Output,P> 类型：元数据 / 核心执行 / Schema / 安全权限 四层结构
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable

from langchain_core.tools import StructuredTool
from pydantic import BaseModel


# ===== 运行时审批回调 =====

# TUI 启动时设置，用于在执行破坏性工具前弹出审批弹窗。
# 签名: async (tool_name: str, args: dict) -> bool
# 返回 True=允许执行，False=拒绝执行
TOOL_APPROVAL_HANDLER: Callable[[str, dict], Awaitable[bool]] | None = None


# ===== 结果数据类型 =====


@dataclass
class PermissionResult:
    """权限检查结果。

    Attributes:
        behavior: 权限行为 — "allow" | "deny" | "ask"
        reason: 拒绝或询问时的原因说明
        updated_input: 权限检查后修改的输入参数（如路径规范化）
    """

    behavior: str = "allow"
    reason: str = ""
    updated_input: dict[str, Any] | None = None


@dataclass
class ValidationResult:
    """输入验证结果。

    Attributes:
        is_valid: 输入是否合法
        errors: 验证失败时的错误消息列表
    """

    is_valid: bool = True
    errors: list[str] = field(default_factory=list)


# ===== 默认值（对应 TS 的 TOOL_DEFAULTS）=====

TOOL_DEFAULTS = {
    "is_enabled": True,
    "is_concurrency_safe": False,  # 默认假定不安全，防止并发问题
    "is_read_only": False,  # 默认假定有写入，需要权限检查
    "is_destructive": False,
}


# ===== 工具定义基类 =====


class ToolDefinition(ABC):
    """所有工具定义的抽象基类。

    子类必须设置类属性 name 并实现以下抽象方法：
        - description() -> str: 工具描述，供 LLM 理解用途
        - input_schema() -> type[BaseModel]: Pydantic 输入模型
        - execute(**kwargs) -> str: 核心执行逻辑

    可选覆盖（带默认值）：
        - aliases, max_result_size, should_defer
        - is_enabled, is_concurrency_safe, is_read_only, is_destructive
        - prompt_description(), validate_input(), check_permissions()
        - to_classifier_input()
    """

    # ===== 元数据（子类直接赋值）=====
    name: str = ""
    aliases: list[str] = []
    max_result_size: int = 100_000
    should_defer: bool = False

    # ===== 安全属性（property，默认取 TOOL_DEFAULTS 保守值）=====

    @property
    def is_enabled(self) -> bool:
        """工具是否启用。"""
        return TOOL_DEFAULTS["is_enabled"]

    @property
    def is_concurrency_safe(self) -> bool:
        """是否可安全并发执行。"""
        return TOOL_DEFAULTS["is_concurrency_safe"]

    @property
    def is_read_only(self) -> bool:
        """是否为只读操作。"""
        return TOOL_DEFAULTS["is_read_only"]

    @property
    def is_destructive(self) -> bool:
        """是否为破坏性操作。"""
        return TOOL_DEFAULTS["is_destructive"]

    # ===== 抽象方法（子类必须实现）=====

    @abstractmethod
    def description(self) -> str:
        """工具描述，供 LLM 理解工具用途。"""
        ...

    @abstractmethod
    def input_schema(self) -> type[BaseModel]:
        """返回 Pydantic 输入模型类。"""
        ...

    @abstractmethod
    def execute(self, **kwargs: Any) -> str:
        """核心执行逻辑。

        Args:
            **kwargs: 经 Pydantic 验证后的输入参数

        Returns:
            工具执行结果字符串
        """
        ...

    # ===== 可选覆盖 =====

    def prompt_description(self) -> str:
        """提供给 LLM 的提示词描述。默认返回 description()。"""
        return self.description()

    def validate_input(self, input_data: BaseModel) -> ValidationResult:
        """验证输入参数。默认通过。"""
        return ValidationResult()

    def check_permissions(self, input_data: BaseModel) -> PermissionResult:
        """检查执行权限。默认允许。"""
        return PermissionResult()

    def to_classifier_input(self) -> str:
        """用于自动分类器的描述文本。默认为空。"""
        return ""


# ===== 工厂函数（对应 TS 的 buildTool）=====


def build_tool(definition: ToolDefinition) -> StructuredTool:
    """工厂函数：将 ToolDefinition 转换为 LangChain StructuredTool。

    执行流程：
        1. Pydantic 模型验证输入
        2. validate_input() 自定义验证
        3. check_permissions() 权限检查
        4. execute() 核心执行
        5. 结果大小截断

    Args:
        definition: 工具定义实例

    Returns:
        可注册到 ToolRegistry / ToolNode 的 StructuredTool

    Raises:
        ValueError: 工具定义为设置 name
    """
    if not definition.name:
        raise ValueError("ToolDefinition.name 不能为空")

    schema_cls = definition.input_schema()

    def _run(**kwargs: Any) -> str:
        # 1. Pydantic 验证
        input_data = schema_cls.model_validate(kwargs)

        # 2. 自定义输入验证
        validation = definition.validate_input(input_data)
        if not validation.is_valid:
            return f"输入验证失败: {'; '.join(validation.errors)}"

        # 3. 权限检查
        permission = definition.check_permissions(input_data)
        if permission.behavior == "deny":
            return f"权限被拒绝: {permission.reason}"

        # 如果权限检查修改了输入，合并到原始输入中
        if permission.updated_input:
            merged = {**input_data.model_dump(), **permission.updated_input}
            input_data = schema_cls.model_validate(merged)

        # 4. 执行核心逻辑
        result = definition.execute(**input_data.model_dump())

        # 5. 结果大小截断
        if isinstance(result, str) and len(result) > definition.max_result_size:
            result = result[: definition.max_result_size] + "\n... [结果已截断]"

        return result

    async def _arun(**kwargs: Any) -> str:
        # 破坏性工具审批：如果设置了审批回调且工具是破坏性的，先请求用户批准
        if definition.is_destructive and TOOL_APPROVAL_HANDLER is not None:
            approved = await TOOL_APPROVAL_HANDLER(definition.name, kwargs)
            if not approved:
                return f"操作被用户拒绝: {definition.name}"
        return _run(**kwargs)

    return StructuredTool.from_function(
        func=_run,
        coroutine=_arun,
        name=definition.name,
        description=definition.description(),
        args_schema=schema_cls,
    )
