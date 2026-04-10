---
title: 协议规范
description: TODO.md 文件格式、标记符号和解析规则
---

本文档定义 TODO.md 文件格式、标记符号和解析规则。

## 文件结构

TODO.md 由以下部分组成：

1. **头部**：标题（`#`）+ 描述块（引用 `>`）
2. **全局控制**：`PAUSE:` 指令
3. **话题**：每个以 `##` 标题开始，包含消息和回复

```markdown
# 共享任务清单

> 协议规则描述...

PAUSE:

## 话题 A

User: 修复登录 bug over

## 话题 B @delete

User: 旧内容
Agent: 已完成
User:
```

## 标记符号

| 标记 | 位置 | 匹配规则 | 含义 |
|------|------|---------|------|
| `over` | 行末 | 不区分大小写，末尾空格可选。正则：`/over\s*$/i` | 用户消息写完，等待 Agent 处理 |
| `[processing]` | 替换 `over` | 精确匹配（非代码上下文） | Agent 正在处理此消息 |
| `[pending]` | Agent 回复末尾 | 精确匹配（非代码上下文） | Agent 有方案但尚未执行 |
| `@delete` | `##` 标题末尾 | 末尾空格可选。正则：`/@delete\s*$/` | 话题应被 Agent 删除 |
| `PAUSE:` | 独立行（顶层区域） | 冒号后有可见字符=暂停，仅空白=不暂停 | 全局暂停/恢复 Agent 处理 |
| `User:` | 行首 | 半角冒号 | 用户消息前缀 |

### 匹配细节

**`over`**：必须是行末最后一个可见标记。仅在代码块（` ``` `）和行内代码（`` ` ``）之外匹配。表格行（`|...|`）排除在外。

```
User: 修复 bug over       ← 匹配（末尾空格OK）
User: 修复 bug Over       ← 匹配（不区分大小写）
User: 修复 bug OVER       ← 匹配
User: 讨论结束 over 了    ← 不匹配（over 后有"了"）
```

**`[processing]`**：Agent 开始处理时替换 `over`，或开始执行任务时替换 `[pending]`。全局同一时刻只应有一个 `[processing]`。操作完成后删除。

**`[pending]`**：话题内只有最后一条 Agent 回复保留 `[pending]`。新回复时删除旧的。

**`@delete`**：必须在 `##` 标题行末尾。整个话题段（从 `##` 到下一个 `##` 或文件末尾之前）被删除。

**`PAUSE:`**：每次迭代检查。冒号后有任何可见字符表示暂停。空或仅空白表示不暂停。

```
PAUSE: true     ← 暂停
PAUSE: 1        ← 暂停
PAUSE: stop     ← 暂停
PAUSE:          ← 不暂停
PAUSE:          ← 不暂停（仅空白）
```

## scan 输出格式

`scan` 命令解析 TODO.md 并返回 JSON。支持两种输出模式和一个可选的清理标志。

### 标志

| 标志 | 效果 |
|------|------|
| （无） | 只读，返回最高优先级话题 + marker |
| `--all` | 只读，返回所有话题 |
| `--clean` | 先删除 `@delete` 话题，再返回结果 |
| `--clean --all` | 删除 `@delete` 话题后，返回所有剩余话题 |

### 默认输出（最高优先级）

```json
{"file": "TODO.md", "marker": "pause"}
```

```json
{"file": "TODO.md", "marker": "processing",
 "topic": {"title": "修复 bug", "line": 10, "end": 25, "marker_line": 15, "context": "User: ..."}}
```

```json
{"file": "TODO.md", "marker": "over",
 "topic": {"title": "修复 bug", "line": 10, "end": 25, "marker_line": 15, "context": "User: ..."},
 "queue_depth": 3}
```

```json
{"file": "TODO.md", "marker": "pending",
 "topic": {"title": "修复 bug", "line": 10, "end": 25, "marker_line": 22, "context": "Agent: 方案..."}}
```

```json
{"file": "TODO.md", "marker": "idle"}
```

### Marker 优先级

| 优先级 | Marker | 条件 |
|--------|--------|------|
| 1 | `pause` | `PAUSE:` 后有可见值 |
| 2 | `processing` | 有话题含 `[processing]` |
| 3 | `over` | 有话题含 `over` |
| 4 | `pending` | 有话题含 `[pending]` |
| 5 | `idle` | 以上均无 |

### `--all` 输出（全部话题）

```json
{
  "file": "TODO.md",
  "paused": false,
  "topics": [
    {
      "title": "修复登录 bug",
      "line": 10,
      "end": 25,
      "delete": false,
      "over": 15,
      "processing": null,
      "pending": null,
      "context": "User: 邮箱有大写字母时登录失败\nUser: 特殊字符也检查一下"
    }
  ]
}
```

### 话题字段（`--all` 模式）

| 字段 | 类型 | 说明 |
|------|------|------|
| `title` | string | 标题文本（不含 `@delete` 标记） |
| `line` | int | 标题行号（1-based） |
| `end` | int | 话题最后一行行号 |
| `delete` | bool | 是否有 `@delete` 标记 |
| `over` | int \| null | 最后一个 `over` 的行号（存在 `[processing]` 时屏蔽为 null） |
| `processing` | int \| null | `[processing]` 标记的行号 |
| `pending` | int \| null | `[pending]` 标记的行号（存在 `over` 或 `[processing]` 时屏蔽为 null） |
| `context` | string \| null | 从标题后第一个非空行到活跃标记行的文本 |

### 规范化规则

- **优先级屏蔽**：`[processing]` > `over` > `[pending]` — 高优先级标记将低优先级的屏蔽为 `null`
- **多个 `over`**：同一话题内只报告最后一个；前面的在 JSON 中被忽略（文件不修改）
- **上下文提取**：遵循同样的优先级；上下文从 `##` 标题后第一个非空行到标记行（含该行，但标记文本被去除）
- **不输出上下文**：`@delete` 话题、无标记的话题

### 解析规则

1. 行号为 **1-based**（与 grep/sed 一致）
2. 代码块（` ``` `）内的标记被忽略
3. 行内代码（`` `...` ``）内容被忽略
4. 表格行（`| ... |`）排除在标记检测之外
5. 每个话题从 `##` 标题延续到下一个 `##` 之前或文件末尾
6. 第一个 `##` 之前的内容为头部区域（包含 `PAUSE:`）

## 处理规则

### `--clean` 行为

指定 `--clean` 时：
1. 解析整个文件
2. 识别带 `@delete` 标记的话题
3. 从文件内容中删除这些话题段
4. 通过临时文件 + `os.replace()` 原子写回
5. 返回不含已删除话题的结果

如果没有 `@delete` 话题，不执行任何文件写入（纯只读）。

### `[processing]` 双重用途

`[processing]` 同时替代 `over` 和 `[pending]`：

- **新消息**：`over` → `[processing]`（Agent 开始处理用户消息）
- **执行任务**：`[pending]` → `[processing]`（Agent 开始执行已规划的任务）

同一时刻全局只应有一个 `[processing]`。

### 同话题多个 over

用户在同一话题内添加多条 over 消息时，只有最后一个是规范值：

```markdown
## 话题
User: 先修按钮
User: 颜色也改下
User: 还有字体 [processing]  ← 最后一个 over → [processing]
User:
```

Agent 的上下文包含上面所有消息（它们是话题内容的一部分）。

### 优先级顺序

1. `[processing]` — 继续处理（Agent 被中断或恢复）
2. `over` — 用户新消息待处理
3. `[pending]` — 已规划任务待执行
4. idle — 无事可做

### 上下文范围

Agent 上下文 = 话题标题 → 活跃标记行（含该行，但标记文本被去除）。标记行之下的内容被排除（可能是用户提交后添加的補充，留待下一轮处理）。
