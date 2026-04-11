---
name: cotodo
description: '共享任务清单协作工作流。通过 TODO.md 实现用户与 Agent 的异步对话式协作：用户追加话题/任务，Agent 循环扫描并处理。Use when: 收到多个 bug 或任务、批量修复、并行协作开发、用户提到 TODO 或任务清单。'
---

# cotodo 协作流程

## 主循环

```
while true:
  result = cotodo scan TODO.md
  if result.marker in ("pause", "idle"):
    askQuestions("等待用户指令")
  else:
    读 result.topic，处理任务，cotodo reply 回结果
```

## scan 获取任务

```bash
cotodo scan TODO.md
```

scan 自动完成初始化、清理和锁定。返回**一个**最高优先级话题：

```json
{
  "file": "TODO.md",
  "marker": "over",
  "topic": {
    "id": "a1b2c3d4",
    "title": "修复登录 bug",
    "context": "User: 登录页面点击没反应\nAgent: 我来检查一下\nUser: 加急处理",
    "summary": null
  }
}
```

| marker | 含义 | 怎么做 |
|--------|------|--------|
| `over` | 用户发了新消息 | context 最后一条 `User:` 是最新指令，据此执行 |
| `processing` | 之前中断的任务 | context 包含进度，继续执行 |
| `pending` | 方案已定，排队执行 | summary 包含方案，按方案执行 |
| `idle` | 无待处理话题 | **必须调用 askQuestions 工具等待用户指令** |
| `pause` | 用户暂停协作 | **必须调用 askQuestions 工具等待用户指令** |

**context**：完整对话（`User: ...\nAgent: ...` 交替），最后一条 `User:` 是最新消息。

**summary**：任务计划或结论摘要；pending 话题的 summary 是待执行方案；null = 尚无。**复杂任务必须写工作计划**，格式：

```
**Summary**

结论要点、解决方案等信息

工作计划：
1. [ ] 第一步
2. [ ] 第二步
3. [ ] 第三步
```

执行完成后将 `[ ]` 改为 `[x]`，保持进度可追踪。

## reply 返回结果

```bash
echo '<json>' | cotodo reply <id>
```

JSON 模板：
```json
{
  "context": "Agent: 回复内容",
  "summary": "更新后的计划/结论"
}
```

| 字段 | 类型 | 说明 |
|------|------|------|
| `context` | string | 回复内容（以 `Agent:` 开头），或压缩后的上下文 |
| `summary` | string\|null | 更新计划/结论（**覆盖**旧 summary）；无变化则省略 |
| `pending` | bool | true = 方案已定，挂起排队；默认 false |
| `compress` | bool | true = context 替换整个对话区；默认 false（追加到对话末尾） |

### 决策指南

- **执行完任务** → context 写结果
- **有新方案或结论** → 更新 summary
- **方案已定、用户认可** → `pending: true`，summary 写方案
- **用户要求压缩上下文** → context 写精简后的核心信息（去除冗余对话，保留关键指令和背景），`compress: true`
- **有问题要问用户** → context 里直接提问（不用 askQuestions）

## 规则

- 一律用 cotodo CLI 读写 TODO.md，不手动编辑
- 每次循环必须重新 scan（用户可能随时追加新话题）
