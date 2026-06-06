# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

ohmycode — 模块化编程助手，基于 LangGraph ReAct Agent + Textual TUI。采用装配模式（Assembly Pattern），各模块通过 Protocol 接口可插拔替换。

## Commands

```bash
# 安装（需要 Python >= 3.11）
python3.11 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"

# 运行测试
pytest                          # 全部测试
pytest tests/test_tools/        # 单个模块测试
pytest -x                       # 遇到第一个失败停止

# 启动应用（需要设置 OPENAI_API_KEY）
python -m ohmycode
```

## Architecture

```
Assembler（组合根，src/ohmycode/assembler.py）
  ├── LLMProvider (Protocol)     → OpenAILLMProvider (src/ohmycode/llm/)
  ├── ToolProvider[] (Protocol)  → StubToolProvider (src/ohmycode/tools/stubs/)
  ├── ContextProvider[] (Protocol) → [IdentityContextProvider, ToolDocsContextProvider] (src/ohmycode/context/)
  └── 构建 → AgentGraph (LangGraph StateGraph) → Textual TUI (src/ohmycode/cli/)
```

**核心数据流：** 用户输入 → Textual InputBar → `graph.astream()` → LangGraph ReAct 循环（agent→tools→agent）→ 流式 token 输出到 ChatArea

**装配模式：** 每个模块实现 `Protocol` 接口（`ContextProvider`、`ToolProvider`、`LLMProvider`）。`Assembler` 在启动时收集所有 Provider，组装系统提示词和工具，构建 Agent 图。任何模块可通过提供不同实现来替换。

## Key Modules

- `src/ohmycode/agent/` — LangGraph ReAct 循环（graph.py 构建图，nodes.py 定义节点和路由）
- `src/ohmycode/cli/` — Textual TUI（app.py 主应用，widgets/ 各组件）
- `src/ohmycode/context/` — 上下文装配引擎（protocols.py 协议，assembler.py 组装器，providers/ 内置提供者）
- `src/ohmycode/tools/` — 工具系统（protocols.py 协议，registry.py 注册表，stubs/ 桩工具）
- `src/ohmycode/llm/` — LLM 提供者（当前仅 OpenAI）
- `src/ohmycode/config/` — TOML 配置加载（settings.py + defaults.toml）
- `src/ohmycode/assembler.py` — 组合根，装配所有模块

## Tech Stack

- Python 3.11+, LangGraph, LangChain (langchain-openai, langchain-core)
- Textual 3.x (TUI), Rich (终端渲染)
- pytest + pytest-asyncio

## Repository

- **Remote:** https://github.com/nbw1090-stack/ohmycode
- **Default branch:** main
