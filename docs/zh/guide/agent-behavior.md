---
title: Agent 行为规范
description: cotodo 协作工作流中的 Agent 行为逻辑
---

定义 Agent 在 cotodo 协作工作流中的行为逻辑。底层文件格式和解析规则见[协议规范](./protocol)。

## 系统架构

```
Human -> TODO.md <- cotodo scan    (读) <- Agent
              ^         cotodo reply (写)
              |
        原子文件操作
```

- **人类**：直接在编辑器里读写 TODO.md
- **Agent**：通过 `cotodo scan` 读取状态，通过 `cotodo reply` 写回回复
- **cotodo**：CLI 工具，两个核心命令：

| 命令 | 行为 |
|------|------|
| `cotodo scan [FILE]` | 解析 TODO.md，自动初始化、清理 @delete、标记最高优先级为 [processing]，返回 JSON |
| `cotodo scan [FILE] --all` | 只读，返回所有话题（调试用） |
| `cotodo reply <id>` | 写入回复（stdin JSON），更新对话 + Summary |

## Agent 循环逻辑

每一轮循环：

```
1. cotodo scan TODO.md → 自动清理 + 标记 [processing] + 返回 JSON
2. 根据 marker + context + summary 处理任务
3. cotodo reply <id> → 写回回复，清除 [processing]
4. 回到 1
```

- `scan` 默认原子操作：初始化（首次）→ 清理 @delete → 标记最高优先级 → 返回 JSON
- `reply` 原子操作：追加对话 + 覆盖 Summary + 管理标记 + 加 User: 占位
- `scan --all` 供调试或需要全局视图时使用

## 行为优先级

`scan` 返回的 `marker` 字段直接告诉 Agent 该做什么：

| marker | 含义 | Agent 行为 |
|--------|------|-----------|
| `"pause"` | PAUSE 全局暂停 | 立即 askQuestions 等待用户，不做任何其他操作 |
| `"processing"` | 有 [processing] 话题 | 恢复并完成上一轮中断的任务 |
| `"over"` | 有 over 话题 | 处理用户新消息 |
| `"pending"` | 有 [pending] 话题 | 执行已规划的任务 |
| `"idle"` | 无待处理内容 | askQuestions 等待用户 |

**说明**：
- @delete 话题已在 scan 阶段被自动删除，不影响 marker 判断
- 优先级选择遵循 protocol 的屏蔽规则：`processing` > `over` > `pending`

## 核心场景

### 场景 A：PAUSE 暂停

**触发**：scan 返回 `marker: "pause"`

**行为**：
1. Agent 立即调用 `askQuestions` 等待用户
2. 不处理任何话题（over / pending / processing 全部搁置）

**说明**：PAUSE 是用户控制 Agent 的全局开关。用户在 TODO.md 里写 `PAUSE: true` 暂停 Agent，清空 `PAUSE:` 后面的内容恢复。

### 场景 B：@delete 清理话题

**触发**：`##` 标题末尾有 `@delete` 标记

**行为**：Agent 使用 `cotodo scan` 时，@delete 话题被自动删除。该话题内的所有标记（over / pending / processing）随话题一起消失，不会被处理。

scan 默认行为即包含清理，无需额外标志。

### 场景 C：恢复 [processing]

**触发**：scan 返回 `marker: "processing"`

**行为**：
1. Agent 读取话题的 `context` 和 `summary`，恢复上下文
2. 继续完成上一轮中断的任务
3. 调用 `cotodo reply` 写入结果

**说明**：`[processing]` 表示 Agent 上一轮开始处理但未完成（可能被中断）。这是最高优先级的话题标记——必须先完成正在进行的工作。

### 场景 D：回复用户新消息（over）

**触发**：scan 返回 `marker: "over"`（scan 默认将 `over` 改为 `[processing]`）

**行为**：
1. 读取话题 `context` 理解用户消息，读取 `summary` 了解当前计划/结论
2. 调用 `cotodo reply` 传入：
   - `context`：对用户的回复（以 `Agent:` 开头）
   - `summary`：更新后的计划/结论（如有变化）
   - `pending`：如果 summary 包含执行计划且用户已认可则为 `true`，否则省略
   - `compress`：如果用户要求压缩上下文则为 `true`（context 为精简后的核心信息），否则省略
3. 多个话题有 over 时，scan 返回第一个，后续轮次处理其余

**回复后状态**：
- 纯回复（无任务）：话题无标记，summary 作为结论
- 有待执行任务：Summary 上有 `[pending]`，下一轮按场景 F 处理

### 场景 E：同话题 [processing] 和 over 并存

**触发**：Agent 正在处理某话题（[processing]），同时用户在该话题追加了新 `over` 消息

**scan 行为**：`processing` 屏蔽 `over`，scan 返回 `marker: "processing"`（而不是 `"over"`）

**Agent 行为**：
1. 当前轮：收到 `processing`，继续完成正在进行的任务
2. 调用 `cotodo reply` 写入结果
3. 下一轮 scan：发现该话题有新的 `over`，返回 `marker: "over"`

**说明**：一致性优先。不能因用户追加消息而中断 in-progress 任务。用户的新消息等当前任务完成后自然被下一轮 scan 捕获。

### 场景 F：执行 [pending] 任务

**触发**：scan 返回 `marker: "pending"`（scan 默认将 `[pending]` 改为 `[processing]`）

**行为**：
1. 读取话题 `summary` 了解执行计划
2. 执行已规划的任务
3. 调用 `cotodo reply` 写入结果和更新后的 summary（标记已完成项）

### 场景 G：[pending] 和 over 并存

**触发**：话题 A 有 `[pending]`，话题 B（或同一话题）有新 `over`

**scan 行为**：
- 同话题内：`over` 屏蔽 `pending`，scan 返回 `marker: "over"`
- 不同话题：`over` 优先级高于 `pending`，scan 仍返回 `marker: "over"`

**Agent 行为**：
1. 先处理 `over`（scan 每轮只返回最高优先级的一个话题，`over` > `pending`）
2. 处理含 `[pending]` 话题的 `over` 时：先移除 `[pending]`，回复后再决定是否重新添加
3. 所有 `over` 回复完后，scan 才会返回 `marker: "pending"`
4. 执行前评估 `[pending]` 方案是否需要调整（用户的 over 可能修正了方案）

**说明**：用户的 over 可能修正已有方案。先对齐需求再执行，避免执行废弃方案。

### 场景 H：idle — 无事可做

**触发**：scan 返回 `marker: "idle"`

**行为**：Agent 调用 `askQuestions` 等待用户下一条指令。

## 标记转换总结

```
用户写完消息加 over
        |
        v
   scan: over -> [processing]    Agent 领取任务
        |
        v
   Agent 处理后调用 reply：
        |
        +-> 纯回复    -> reply 移除 [processing]，写消息 + User:
        |
        +-> 有方案    -> reply 移除 [processing]，写消息
        |                + Summary [pending] + User:
        |
        v
   scan: [pending] -> [processing]    Agent 领取方案
        |
        v
   Agent 执行后调用 reply：
        |
        v
   reply 移除 [processing]，写结果 + 更新 Summary + User:
```
