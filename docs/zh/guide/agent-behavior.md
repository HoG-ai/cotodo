---
title: Agent 行为规范
description: cotodo 协作工作流中的 Agent 行为逻辑
---

定义 Agent 在 cotodo 协作工作流中的行为逻辑。底层文件格式和解析规则见[协议规范](./protocol)。

## 系统架构

```
Human -> TODO.md <- cotodo scan (只读) <- Agent
              ^
        Agent 通过终端命令编辑 (sed/printf/cat)
```

- **人类**：直接在编辑器里读写 TODO.md
- **Agent**：通过 `cotodo scan` 获取结构化状态（JSON），通过终端命令编辑文件
- **cotodo**：CLI 工具，`scan` 命令有四种模式组合：

| 命令 | 行为 |
|------|------|
| `cotodo scan` | 只读，返回最高优先级的一个话题 + marker |
| `cotodo scan --clean` | 删除 @delete 话题后，返回最高优先级话题 |
| `cotodo scan --all` | 只读，返回所有话题的完整列表 |
| `cotodo scan --clean --all` | 删除 @delete 话题后，返回所有话题 |

## Agent 循环逻辑

每一轮循环：

```
1. cotodo scan --clean → 获取 JSON（marker + 最高优先级话题），同时清理 @delete 话题
2. 根据 marker 决定行为
3. 执行 marker、编辑 TODO.md
4. 回到 1
```

Agent 日常循环只用 `scan --clean`。`scan --all` 供调试或需要全局视图时使用。

## 行为优先级

`scan --clean` 返回的 `marker` 字段直接告诉 Agent 该做什么：

| marker | 含义 | Agent 行为 |
|--------|------|-----------|
| `"pause"` | PAUSE 全局暂停 | 立即 askQuestions 等待用户，不做任何其他操作 |
| `"processing"` | 有 [processing] 话题 | 恢复并完成上一轮中断的任务 |
| `"over"` | 有 over 话题 | 处理用户新消息 |
| `"pending"` | 有 [pending] 话题 | 执行已规划的任务 |
| `"idle"` | 无待处理内容 | askQuestions 等待用户 |

**说明**：
- @delete 话题已在 `--clean` 阶段被删除，不影响 marker 判断
- 优先级选择遵循 protocol 的屏蔽规则：`processing` > `over` > `pending`
- `over` 时返回 `queue_depth` 告知还有多少话题排队

## 核心场景

### 场景 A：PAUSE 暂停

**触发**：scan 返回 `marker: "pause"`

**行为**：
1. Agent 立即调用 `askQuestions` 等待用户
2. 不处理任何话题（over / pending / processing 全部搁置）

**说明**：PAUSE 是用户控制 Agent 的全局开关。用户在 TODO.md 里写 `PAUSE: true` 暂停 Agent，清空 `PAUSE:` 后面的内容恢复。

### 场景 B：@delete 清理话题

**触发**：`##` 标题末尾有 `@delete` 标记

**行为**：Agent 使用 `cotodo scan --clean` 时，@delete 话题被自动删除。该话题内的所有标记（over / pending / processing）随话题一起消失，不会被处理。

**`scan` vs `scan --clean`**：
- `scan`（无 flag）：只读，返回 JSON 中 `delete: true`，文件不变
- `scan --clean`：先删除 @delete 话题，再返回剩余话题的 JSON。删除的话题不出现在返回结果中

**说明**：@delete 是用户主动放弃该话题的信号。Agent 循环中应始终使用 `scan --clean`，一步完成清理+扫描。

### 场景 C：恢复 [processing]

**触发**：scan 返回 `marker: "processing"`

**行为**：
1. Agent 读取该话题的 `context`（从标题到 [processing] 行的内容），恢复上下文
2. 继续完成上一轮中断的任务
3. 完成后删除 `[processing]` 标记，写入结果

**说明**：`[processing]` 表示 Agent 上一轮开始处理但未完成（可能被中断）。这是最高优先级的话题标记——必须先完成正在进行的工作。

### 场景 D：回复用户新消息（over）

**触发**：scan 返回 `marker: "over"`

**行为**：
1. 将该行的 `over` 改为 `[processing]`（让用户看到正在处理）
2. 读取话题 `context` 理解用户消息
3. 在话题内写 `Agent:` 回复
4. 如果是可执行的任务：回复末尾加 `[pending]`（方案暂不执行，等用户确认）
5. 删除 `[processing]`，追加空行和 `User:` 占位
6. 多个话题有 over 时，从上到下逐个处理

**回复后状态**：
- 纯回复（无任务）：话题回到无标记状态
- 有待执行任务：话题有 `[pending]` 标记，下一轮按场景 F 处理

### 场景 E：同话题 [processing] 和 over 并存

**触发**：Agent 正在处理某话题（[processing]），同时用户在该话题追加了新 `over` 消息

**scan 行为**：`processing` 屏蔽 `over`，scan 返回 `marker: "processing"`（而不是 `"over"`）

**Agent 行为**：
1. 当前轮：收到 `processing`，继续完成正在进行的任务
2. 完成后删除 `[processing]`
3. 下一轮 scan：发现该话题有新的 `over`，返回 `marker: "over"`

**说明**：一致性优先。不能因用户追加消息而中断 in-progress 任务。用户的新消息等当前任务完成后自然被下一轮 scan 捕获。

### 场景 F：执行 [pending] 任务

**触发**：scan 返回 `marker: "pending"`

**行为**：
1. 将 `[pending]` 改为 `[processing]`
2. 执行该话题中规划的任务
3. 完成后删除 `[processing]`，在话题内写简要执行结果

### 场景 G：[pending] 和 over 并存

**触发**：话题 A 有 `[pending]`，话题 B（或同一话题）有新 `over`

**scan 行为**：
- 同话题内：`over` 屏蔽 `pending`，scan 返回 `marker: "over"`
- 不同话题：`over` 优先级高于 `pending`，scan 仍返回 `marker: "over"`

**Agent 行为**：
1. 先处理 `over`（scan 每轮只返回最高优先级的一个话题，`over` > `pending`）
2. 所有 `over` 回复完后，scan 才会返回 `marker: "pending"`
3. 执行前评估 `[pending]` 方案是否需要调整（用户的 over 可能修正了方案）
4. 方案不变：直接执行
5. 方案变更：更新方案内容，重新加 `[pending]`，等下轮执行

**说明**：用户的 over 可能修正已有方案。先对齐需求再执行，避免执行废弃方案。

### 场景 H：idle — 无事可做

**触发**：scan 返回 `marker: "idle"`

**行为**：Agent 调用 `askQuestions` 等待用户下一条指令。

## 标记转换总结

```
用户写完消息加 over
        |
        v
   over -> [processing]    Agent 开始处理
        |
        +-> 纯回复 -> 删除 [processing]，写 Agent: 回复 + User:
        |
        +-> 有任务 -> 删除 [processing]，写 Agent: 方案 [pending] + User:
                                |
                                v
                    [pending] -> [processing]    Agent 开始执行
                                |
                                v
                        删除 [processing]，写执行结果
```
