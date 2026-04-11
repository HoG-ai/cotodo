---
name: cotodo
description: '共享任务清单协作工作流。通过 TODO.md 实现用户与 Agent 的异步对话式协作：用户追加话题/任务，Agent 循环扫描并处理。Use when: 收到多个 bug 或任务、批量修复、并行协作开发、用户提到 TODO 或任务清单。'
---

# cotodo 协作流程

## 主循环

```
while true:
  result = cotodo scan --take    # 原子：读状态 + 标 [processing]
  if result.marker == "pause"  → askQuestions 暂停
  if result.marker == "idle"   → askQuestions 等待用户
  if result.marker in ("over", "pending", "processing") → 处理话题
```

## 处理话题

1. 从 `result.topic.context` 和 `result.topic.summary` 了解任务
2. 执行工作（修代码、查资料等）
3. 回复（用 scan 输出的 `id`）：
   ```bash
   echo '{"message": "回复内容", "summary": "计划/结论", "pending": true}' | cotodo reply <id>
   ```

## reply 字段

| 字段 | 说明 |
|------|------|
| `message` | 回复文本，自动加 `Agent:` 前缀 |
| `summary` | 覆盖写 `> **Summary**` 区，`null` 不动 |
| `pending` | `true` = 有方案暂不执行，`false` = 已完成或无需标记 |

## 其他命令

- `cotodo init` — 创建 TODO.md 模板（自动加 .gitignore）
- `cotodo scan --clean` — 删除 `@delete` 话题
- `cotodo reply --compress <id>` — 压缩模式，message 替换整个对话区

## 注意

- 一律用 cotodo CLI 读写 TODO.md，不用其他方式
- 有疑问直接 `cotodo reply <id>` 提问，不用 askQuestions
