# ohmycode

> 模块化编程助手 — 基于 LangGraph ReAct Agent + Textual TUI

ohmycode 是一个在终端中运行的 AI 编程助手。它采用**装配模式（Assembly Pattern）**将各模块通过 `Protocol` 接口可插拔组合，具备完整的 ReAct 推理-行动循环、上下文工程引擎、流式输出和工具调用能力。

---

## ✨ 功能特性

| 特性 | 说明 |
|------|------|
| 🧠 ReAct Agent 循环 | 基于 LangGraph StateGraph，支持多轮推理-工具调用-观察循环 |
| 📦 装配模式 | `Assembler` 组合根 + `Protocol` 接口，模块可插拔替换 |
| 🧩 上下文工程 | 多个 ContextProvider 按优先级自动组装系统提示词 |
| 🔧 工具系统 | 可扩展的工具注册表，内置 echo / read_file / list_files |
| 🖥️ 终端 TUI | 基于 Textual 3.x 的现代终端 UI，支持流式输出 |
| ⚡ 实时状态 | 空闲 / 思考中 / 执行工具中 三态状态栏 |
| 🔍 工具面板 | 可折叠的工具调用详情面板，实时显示工具调用和结果 |
| 📐 TOML 配置 | 分层配置：LLM 从环境变量，Agent/Tools 从 TOML 文件 |

---

## 🏗️ 架构总览

```
                        ┌─────────────────────────────────────────┐
                        │            Assembler (组合根)             │
                        │          assembler.py                    │
                        ├─────────────────────────────────────────┤
                        │                                         │
                        │  ┌─────────────┐  ┌──────────────────┐  │
         ┌──────────────┤  │LLMProvider  │  │ ContextProvider[]│  │
         │              │  │ (Protocol)  │  │   (Protocol)     │  │
         │              │  └──────┬──────┘  └───────┬──────────┘  │
         │              │         │                 │              │
         │              │         ▼                 ▼              │
         │              │  ┌──────────────────────────────┐       │
         │              │  │    build_react_graph()        │       │
         │              │  │                              │       │
         │              │  │  ┌────────┐    ┌───────────┐ │       │
         │              │  │  │ Agent  │◄──►│  Tools    │ │       │
         │              │  │  │ Node   │    │  Node     │ │       │
         │              │  │  └────────┘    └───────────┘ │       │
         │              │  └──────────────────────────────┘       │
         │              │         │                 ▲              │
         │              │  ┌──────┴──────┐  ┌───────┴──────────┐  │
         │              │  │ToolProvider[]│  │ System Prompt    │  │
         │              │  │ (Protocol)  │  │ Assembled        │  │
         │              │  └─────────────┘  └──────────────────┘  │
         │              └─────────────────────────────────────────┘
         │                          │
         ▼                          ▼
┌─────────────────────────────────────────────────────────────────┐
│                     Textual TUI (cli/)                          │
│  ┌──────────┐  ┌───────────┐  ┌──────────┐  ┌──────────────┐   │
│  │ ChatArea │  │ ToolPanel │  │StatusBar │  │  InputBar    │   │
│  │ 聊天区域  │  │ 工具面板   │  │ 状态栏   │  │  输入栏      │   │
│  └──────────┘  └───────────┘  └──────────┘  └──────────────┘   │
└─────────────────────────────────────────────────────────────────┘
```

---

## 🔄 Agent Loop（ReAct 循环）

Agent 采用经典的 **ReAct (Reason-Act-Observe)** 模式，由 LangGraph `StateGraph` 驱动：

```
                    ┌───────────────────────────────────────┐
                    │           LangGraph ReAct 循环         │
                    │                                       │
  START ──────► ┌────────┐                           ┌───────────┐
                │        │     should_continue()     │           │
                │ Agent  │ ──────────────────────►   │    END    │
                │ Node   │    无 tool_calls 时        │           │
                │        │ ◄──────────────────────   └───────────┘
                └───┬────┘                           ▲
                    │                                │
                    │ 有 tool_calls                   │ 无 tool_calls
                    ▼                                │
               ┌──────────┐                          │
               │          │    执行完毕，              │
               │  Tools   │ ──── 结果回传 ───────►  ┌──┴───┐
               │  Node    │                        │ Agent │
               │          │                        │ Node  │
               └──────────┘    进入下一轮推理 ◄──── └──────┘
                                              (循环继续)
```

### 工作流程

1. **用户输入** → `HumanMessage` 进入 `MessagesState`
2. **Agent Node** → 注入系统提示词，调用 LLM（已绑定工具）
3. **路由判断** (`should_continue`)：
   - LLM 返回 `tool_calls` → 路由到 **Tools Node**
   - LLM 无 `tool_calls` → 输出最终回复，循环结束
4. **Tools Node** → 执行工具调用，结果作为 `ToolMessage` 回传
5. **回到 Agent Node** → LLM 根据工具结果继续推理
6. 重复 3-5，直到 LLM 认为无需再调用工具

### 关键文件

| 文件 | 职责 |
|------|------|
| [graph.py](src/ohmycode/agent/graph.py) | 构建 `StateGraph`，定义节点和边 |
| [nodes.py](src/ohmycode/agent/nodes.py) | `call_model` 节点（调用 LLM）和 `should_continue` 路由函数 |
| [state.py](src/ohmycode/agent/state.py) | 状态定义，使用 LangGraph 内置 `MessagesState` |

---

## 🧩 上下文工程（Context Engineering）

上下文工程负责**自动组装系统提示词**，让每个模块都能向 Agent 注入自己的上下文信息。

### 装配流程

```
┌────────────────────┐    ┌─────────────────────┐
│ IdentityProvider   │    │  ToolDocsProvider    │     可扩展更多 ...
│ 优先级: 10         │    │  优先级: 50          │     ┌───────────────┐
│ (角色定义)          │    │  (工具文档)          │     │ CustomProvider │
└────────┬───────────┘    └──────────┬──────────┘     └───────┬───────┘
         │                           │                        │
         ▼                           ▼                        ▼
    ┌──────────────────────────────────────────────────────────────┐
    │                  assemble_system_prompt()                     │
    │                                                              │
    │  1. 收集所有 SystemPromptPart                                 │
    │  2. 按 name 去重（后者覆盖前者）                               │
    │  3. 按 priority 升序排列                                      │
    │  4. "\n\n" 拼接为完整系统提示词                                │
    └──────────────────────────┬───────────────────────────────────┘
                               │
                               ▼
                    ┌─────────────────────┐
                    │  完整 System Prompt  │
                    │                     │
                    │  # 身份定义 (pri=10) │
                    │  你是 ohmycode ...   │
                    │                     │
                    │  # 工具文档 (pri=50) │
                    │  可用工具列表: ...    │
                    └─────────────────────┘
```

### 内置 Provider

| Provider | 优先级 | 内容 |
|----------|--------|------|
| `IdentityContextProvider` | 10 | Agent 身份和角色定义 |
| `ToolDocsContextProvider` | 50 | 动态生成的可用工具列表和描述 |

### 扩展方式

实现 `ContextProvider` Protocol 即可注入自定义上下文：

```python
from ohmycode.context.protocols import ContextProvider
from ohmycode.context.parts import SystemPromptPart

class ProjectContextProvider:
    """注入项目文档作为上下文。"""

    def system_prompt_parts(self) -> list[SystemPromptPart]:
        return [SystemPromptPart(
            name="project_docs",
            priority=30,
            content="## 项目文档\n..."
        )]
```

---

## 📦 模块结构

```
src/ohmycode/
├── __main__.py              # 入口：加载配置 → 装配模块 → 启动 TUI
├── assembler.py             # 组合根：装配所有模块
├── types.py                 # 共享类型（AgentState 枚举）
│
├── agent/                   # 🧠 ReAct Agent
│   ├── graph.py             #   StateGraph 构建（节点 + 边 + 路由）
│   ├── nodes.py             #   call_model + should_continue
│   └── state.py             #   MessagesState
│
├── cli/                     # 🖥️ Textual TUI
│   ├── app.py               #   主应用（流式 Agent 调用）
│   ├── styles/
│   │   └── app.tcss         #   全局样式
│   └── widgets/
│       ├── chat_area.py     #   聊天历史区域（只读 TextArea）
│       ├── input_bar.py     #   输入栏（TextArea + 发送按钮）
│       ├── status_bar.py    #   状态栏（空闲/思考/执行工具）
│       └── tool_panel.py    #   工具调用面板（可折叠）
│
├── context/                 # 🧩 上下文工程
│   ├── protocols.py         #   ContextProvider Protocol
│   ├── assembler.py         #   系统提示词装配引擎
│   ├── parts.py             #   SystemPromptPart + ContextSnippet
│   └── providers/
│       ├── identity.py      #   身份上下文
│       └── tool_docs.py     #   工具文档上下文
│
├── tools/                   # 🔧 工具系统
│   ├── protocols.py         #   ToolProvider Protocol
│   ├── registry.py          #   ToolRegistry 注册表
│   └── stubs/
│       ├── echo.py          #   echo 工具（测试用）
│       ├── read_file.py     #   文件读取工具
│       └── list_files.py    #   目录列表工具
│
├── llm/                     # 🤖 LLM 提供者
│   ├── protocols.py         #   LLMProvider Protocol
│   └── openai_provider.py   #   OpenAI 实现
│
└── config/                  # ⚙️ 配置系统
    ├── settings.py          #   Settings 数据类
    └── defaults.toml        #   默认配置值
```

---

## 🚀 快速开始

### 环境要求

- Python >= 3.11
- OpenAI API Key（或兼容的 API 端点）

### 安装

```bash
# 克隆仓库
git clone https://github.com/nbw1090-stack/ohmycode.git
cd ohmycode

# 创建虚拟环境并安装
python3.11 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

### 配置

```bash
# 复制环境变量模板
cp .env.example .env

# 编辑 .env，填入你的 API Key
# OPENAI_API_KEY=sk-...
# OPENAI_MODEL=gpt-4o-mini          # 可选，默认 gpt-4o-mini
# OPENAI_BASE_URL=https://...       # 可选，自定义 API 端点
# OPENAI_TEMPERATURE=0.0             # 可选，默认 0.0
```

### 运行

```bash
python -m ohmycode
```

### 测试

```bash
pytest                    # 运行全部测试
pytest tests/test_tools/  # 运行单个模块测试
pytest -x                 # 遇到第一个失败停止
```

---

## 🔌 插拔扩展

ohmycode 的每个核心模块都通过 `Protocol` 接口定义，可以独立替换：

### 替换 LLM 提供者

```python
from ohmycode.llm.protocols import LLMProvider

class AnthropicLLMProvider:
    """替换为 Claude 模型。"""
    def chat_model(self, tools):
        # 返回 LangChain ChatModel 实例
        ...
```

### 添加新工具

```python
from langchain_core.tools import tool

@tool
def search_web(query: str) -> str:
    """搜索互联网。"""
    ...
```

### 添加上下文提供者

```python
from ohmycode.context.parts import SystemPromptPart

class GitContextProvider:
    """注入 Git 仓库信息。"""
    def system_prompt_parts(self):
        return [SystemPromptPart(
            name="git_info",
            priority=40,
            content=f"当前分支: {get_git_branch()}"
        )]
```

---

## 🛠️ 技术栈

| 层级 | 技术 |
|------|------|
| Agent 框架 | LangGraph 0.2+ |
| LLM 集成 | LangChain (langchain-openai, langchain-core) |
| TUI 框架 | Textual 3.x |
| 终端渲染 | Rich 13+ |
| 配置 | TOML + python-dotenv |
| 测试 | pytest + pytest-asyncio |
| Python | 3.11+ |

---

## 📊 完整数据流

```
用户输入
  │
  ▼
┌──────────┐    HumanMessage     ┌──────────────┐
│ InputBar │ ──────────────────► │ _conversation │
│ (TUI)    │                    │   (消息列表)    │
└──────────┘                    └──────┬───────┘
                                       │
                                       ▼
                            ┌─────────────────────┐
                            │  graph.astream()     │
                            │  (LangGraph 流式调用) │
                            └──────────┬──────────┘
                                       │
                    ┌──────────────────┼──────────────────┐
                    │                  │                   │
                    ▼                  ▼                   ▼
             ┌──────────┐      ┌───────────┐      ┌───────────┐
             │ messages │      │  updates   │      │  events   │
             │  事件流   │      │   事件流    │      │           │
             └─────┬────┘      └─────┬─────┘      └───────────┘
                   │                 │
                   ▼                 ▼
            ┌────────────┐    ┌────────────┐
            │  ChatArea   │    │  StatusBar  │
            │ 逐token显示 │    │ 状态切换    │
            └────────────┘    │ ToolPanel   │
                              │ 工具调用详情 │
                              └────────────┘
```

---

## 📄 License

MIT
