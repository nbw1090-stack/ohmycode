# ohmycode Q&A — 会话与上下文管理开发过程中的问题与解决方案

> 记录在实现 Session 管理、JSONL 持久化、上下文压缩过程中遇到的实际问题、根因分析和最终解决方案。

---

## Q1: JSONL 文件中为什么只记录了用户消息，Agent 的回复没有被保存？

**现象**：用户进行了多轮对话，但 JSONL 文件中只看到 `user` 类型的 message 记录，没有任何 `assistant` 类型的记录。

**根因**：`_run_agent` 在流式处理结束后，只把 `full_response`（拼接的纯文本字符串）作为一条 `AIMessage` 保存。但 `full_response` 仅在 `messages` 流事件中被拼接——如果 token 流没有触发（比如走了 `updates` 路径），`full_response` 为空，就不会保存任何回复。

更关键的是，这种方式完全丢失了：
- 带 `tool_calls` 的 `AIMessage`（工具调用请求）
- `ToolMessage`（工具执行结果）
- 中间产生的多条 `AIMessage`（工具调用后的分析文本）

**解决方案**：从 LangGraph 的 `updates` 流中收集完整的消息链。每个节点完成后，`updates` 事件包含该节点产出的新消息。用一个 `turn_new_messages` 列表按顺序收集所有 `AIMessage` 和 `ToolMessage`，turn 结束后批量同步到 Session。

---

## Q2: JSONL 文件中 `prompt_history` 记录夹在消息之间，打断了消息流

**现象**：JSONL 文件的顺序是 `user message → prompt_history → assistant message → prompt_history → ...`，`prompt_history` 打断了消息记录的连续性。

**根因**：`_handle_user_input` 中在 `push_message` 之后立即调用 `push_prompt_entry` 和 `save_prompt_entry`，把 prompt_history 写入 JSONL。

**解决方案**：
- 正常 turn 过程中不再写 `prompt_history`
- 仅在**上下文压缩时**，把被移除的用户消息迁移到 `prompt_history` 中保存

这样 JSONL 在正常运行时只包含 `message` 记录，`prompt_history` 只在压缩后的全量快照中出现。

---

## Q3: 如何恢复之前关闭的会话？

**现象**：关闭 TUI 后重新启动 `python -m ohmycode`，总是创建新会话，无法继续之前的对话。

**根因**：`__main__.py` 的启动流程只调用 `create_session()`，没有提供加载已有会话的入口。

**解决方案**：给 `__main__.py` 添加 `--resume` 命令行参数：

```bash
python -m ohmycode --resume              # 恢复最近的会话
python -m ohmycode --resume latest       # 同上
python -m ohmycode --resume <session-id> # 恢复指定会话
python -m ohmycode --resume <file-path>  # 从文件加载
```

`SessionStore.load_session()` 支持三级引用解析：别名（latest/last/recent）→ 文件路径 → Session ID。

---

## Q4: `Session.fork` 字段和方法名冲突导致 `TypeError: 'NoneType' object is not callable`

**现象**：调用 `session.fork(branch_name="test")` 时报 `TypeError: 'NoneType' object is not callable`。

**根因**：Session 类中 `fork` 字段（`SessionFork | None`）和 `fork()` 方法同名。Python 中实例属性会遮蔽（shadow）同名方法——`self.fork` 返回的是字段值 `None`，而不是方法。

**解决方案**：将方法重命名为 `create_fork()`，字段保持 `fork` 不变：

```python
# 字段
self.fork: SessionFork | None = None

# 方法（重命名）
def create_fork(self, branch_name: str | None = None) -> Session:
    ...
```

---

## Q5: `test_latest_alias` 测试间歇性失败——两个 session 的 `updated_at_ms` 相同

**现象**：`assert latest.session_id == s2.session_id` 失败，因为两个 session 在同一毫秒内创建，`updated_at_ms` 完全相同，排序不确定。

**根因**：`Session._touch()` 使用 `int(time.time() * 1000)` 生成时间戳。两个 `create_session()` 在同一毫秒内完成时，时间戳相同。

**解决方案**：
1. 测试中添加 `time.sleep(0.01)` 确保时间戳不同
2. `list_sessions()` 使用三级排序：`updated_at_ms` → 文件 mtime → session_id，降低冲突概率

---

## Q6: 为什么一次对话失败后，后续所有对话都返回同样的 400 错误？

**现象**：
```
Error code: 400 - An assistant message with 'tool_calls' must be followed by
tool messages responding to each 'tool_call_id'. (insufficient tool messages
following tool_calls message)
```
一次失败后，每次用户输入新问题都返回这个同样的错误。

**根因**（三个关联 bug）：

1. **`seen_count` 索引错位导致消息收集失败**：LangGraph `updates` 模式下，每个节点事件的 `messages` **只包含该节点产出的新消息**（不是累积列表）。但 `seen_count` 把它当成了累积列表——第一个 agent 节点 `seen_count` 被设为 1，之后 tools 节点的 `messages` 只有 `[ToolMessage]`，`messages[1:]` 变成空列表，ToolMessage 丢失。

2. **半同步后消息链断裂**：只有 `AIMessage(tool_calls)` 被同步到 Session，没有对应的 `ToolMessage`。发送给 LLM API 时触发 400。

3. **错误后无恢复机制**：`except` 块只显示错误，不回滚 Session。损坏的消息序列永久留在 `session.messages` 中，后续每个 turn 都发送相同的坏序列。

**解决方案**（三层防御）：

| 层级 | 措施 | 位置 |
|---|---|---|
| **收集层** | 移除 `seen_count`，直接遍历 updates 中每个节点的所有消息 | `_run_agent` |
| **校验层** | 同步前检查孤立 tool_calls，截断修复 | `_find_orphaned_tool_calls` |
| **恢复层** | `except` 块回滚 session.messages 到 turn 前的快照 + 全量覆盖 JSONL | `_run_agent` |
| **加载层** | `load_session` 时自动检测并修复消息链 | `_validate_and_repair_messages` |

---

## Q7: 为什么 `--resume` 恢复的会话立即触发 400 错误？

**现象**：`python -m ohmycode --resume latest` 启动后，第一条消息就返回 400 错误。

**根因**：上一次会话因 Bug Q6 导致 JSONL 中保存了 `AIMessage(tool_calls)` 但没有对应的 `ToolMessage`。`load_session` 原样加载这个损坏的消息链，第一轮对话发送给 LLM 时就触发了 400。

**解决方案**：在 `SessionStore._load_from_path()` 中增加 `_validate_and_repair_messages()`，加载时扫描消息链，如果发现 AIMessage 有 tool_calls 但没有后续 ToolMessage，截断到该消息之前。

---

## Q8: 上下文压缩的摘要生成需要调用 LLM 吗？会产生额外成本吗？

**答案**：不需要，零成本。

摘要生成 `summarize_messages()` 是一个**纯函数**——不调用 LLM，只做模板填充。它通过以下方式提取信息：
- **计数**：统计 user/assistant/tool 消息数 → Scope
- **去重排序**：提取工具名列表 → Tools mentioned
- **取最近 N 条**：收集最近用户请求 → Recent user requests
- **关键词匹配**：检测 todo/next/pending → Pending work
- **路径 + 扩展名检测**：提取文件路径 → Key files
- **取最后一条文本**：推断当前工作 → Current work
- **逐条截断**：每条消息压缩为一行 → Key timeline

整个过程确定性、零延迟、零 API 成本。

---

## Q9: 多次压缩后，早期的摘要信息会丢失吗？

**答案**：不会。`merge_compact_summaries()` 在合并时区分标注旧摘要和新摘要：

```xml
<summary>
- Previously compacted context: ...
- Newly compacted context: ...
- Key timeline: (保留最新的时间线，旧的被丢弃以防止膨胀)
</summary>
```

旧摘要的高亮信息（Scope、Key files、Tools mentioned 等）被保留在 "Previously compacted context" 中，只有旧时间线被丢弃（因为时间线容易膨胀，且新时间线已包含最新状态）。

如果合并后的摘要仍然过长，`SummaryCompressionBudget` 会按四级优先级（核心信息 > 章节标题 > 列表项 > 其他）在预算内保留最重要的行。

---

## Q10: JSONL 文件的存储路径是什么？如何保证多工作区隔离？

**存储路径**：
```
{当前工作目录}/.ohmycode/sessions/{16位十六进制fingerprint}/session-{ts}-{id}.jsonl
```

**多工作区隔离**：使用 FNV-1a 哈希将工作区绝对路径映射为 16 字符十六进制字符串作为目录名。不同项目目录产生不同的 fingerprint，session 文件互不干扰。

**双重校验**：
1. 目录隔离：不同 fingerprint → 不同目录
2. 内容校验：`_validate_workspace()` 检查 JSONL 中的 `workspace_root` 是否匹配当前工作区，即使文件被复制到其他目录也会被拒绝

---

## Q11: 会话文件的日志轮转策略是什么？

**策略**：
- 全量快照时检查文件大小，超过 **256KB** 触发轮转
- 轮转：将当前文件重命名为 `.rot-{timestamp}.jsonl`
- 最多保留 **3 个**历史轮转文件，更早的自动删除
- 正常追加写入（`save_message`）不触发轮转，只追加一行

轮转文件用于数据恢复——如果新的 JSONL 损坏，可以从轮转文件恢复到上一个完整状态。
