"""预定义的 Span 名称常量。

统一管理所有 span 名称，避免硬编码字符串散落在各处。
遵循 OTel 命名规范：使用点号分隔的命名空间格式。
"""


# ===== 对话级别 =====
TRACE_CONVERSATION = "ohmycode.conversation"

# ===== Agent 节点 =====
SPAN_AGENT_CALL_MODEL = "ohmycode.agent.call_model"
SPAN_AGENT_TOOLS = "ohmycode.agent.tools"
SPAN_AGENT_SHOULD_CONTINUE = "ohmycode.agent.should_continue"

# ===== LLM 调用 =====
SPAN_LLM_INVOKE = "ohmycode.llm.invoke"

# ===== 工具调用 =====
SPAN_TOOL_PREFIX = "ohmycode.tools"

# ===== Span 事件名称 =====
EVENT_ROUTING_DECISION = "routing_decision"
EVENT_TOOL_START = "tool_start"
EVENT_TOOL_END = "tool_end"
EVENT_ERROR = "error"

# ===== Span 属性键 =====
ATTR_MODEL = "llm.model"
ATTR_PROMPT_TOKENS = "llm.prompt_tokens"
ATTR_COMPLETION_TOKENS = "llm.completion_tokens"
ATTR_TOTAL_TOKENS = "llm.total_tokens"
ATTR_TOOL_NAME = "tool.name"
ATTR_TOOL_ARGS = "tool.args_summary"
ATTR_ERROR_TYPE = "error.type"
ATTR_ERROR_MESSAGE = "error.message"
ATTR_MODULE = "module"
ATTR_DECISION = "decision"
ATTR_CONVERSATION_ID = "conversation.id"
