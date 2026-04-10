# 测试指南

## 快速开始

```bash
# 运行全部自动化测试
PYTHONPATH=skills/cotodo python -m pytest tests/ -v

# 仅运行 fixture 集成测试
PYTHONPATH=skills/cotodo python -m pytest tests/test_fixtures.py -v

# 仅运行单元测试
PYTHONPATH=skills/cotodo python -m pytest tests/test_parser.py -v
```

## 测试结构

```
tests/
├── test_parser.py        # 单元测试（内联构造数据，41 个用例）
├── test_fixtures.py      # Fixture 集成测试（29 个用例）
└── fixtures/
    ├── TODO_full.md      # 17 个场景：所有标记 + 边界情况
    ├── TODO_paused.md    # PAUSE 激活状态
    ├── TODO_idle.md      # 全 idle（无任何标记）
    ├── TODO_priority.md  # Marker 优先级链验证
    └── TODO_clean.md     # @delete 清理（破坏性操作）
```

## 手动测试

以下命令均在项目根目录执行。

### 1. 全场景解析（`--all` 模式）

```bash
PYTHONPATH=skills/cotodo python -m cotodo scan tests/fixtures/TODO_full.md --all
```

**验证要点：**
- 输出 17 个话题
- `paused: false`
- T1–T3：`over` 有值，`context` 中标记文本已去除
- T4–T7：`over` 为 null（非行尾 / 代码块内 / 内联代码内 / 表格行内）
- T8–T9：`processing` 有值，`over` 为 null（被遮盖）
- T10：`pending` 有值
- T11：`over` 有值，`pending` 为 null（被 over 遮盖）
- T12：`delete: true`，`context: null`
- T13：仅报告最后一个 `over` 的行号
- T14：所有标记均为 null
- T15：`processing` 有值，`over` 和 `pending` 均为 null
- T16：空话题，全部 null
- T17：3 行 context，最后一行 `over` 文本已去除

### 2. 默认模式 — 最高优先级 Marker

```bash
PYTHONPATH=skills/cotodo python -m cotodo scan tests/fixtures/TODO_full.md
```

**期望结果：** `marker: "processing"`，话题为 T8（含 `[processing]`）

### 3. PAUSE 状态

```bash
PYTHONPATH=skills/cotodo python -m cotodo scan tests/fixtures/TODO_paused.md
```

**期望结果：** `marker: "pause"` — 无 topic 字段，PAUSE 覆盖一切。

### 4. 全 Idle 状态

```bash
PYTHONPATH=skills/cotodo python -m cotodo scan tests/fixtures/TODO_idle.md
```

**期望结果：** `marker: "idle"` — 所有话题都没有活跃标记。

### 5. 优先级链

```bash
PYTHONPATH=skills/cotodo python -m cotodo scan tests/fixtures/TODO_priority.md
```

**期望结果：** `marker: "processing"`，话题为 P3（processing 优先于 over 和 pending）。

验证完整优先级链的方法 — 逐步移除标记：
1. 删除 P3 的 `[processing]` → 期望 `marker: "over"`（P2 有 over）
2. 再删除 P2 的 `over` → 期望 `marker: "pending"`（P1 有 pending）
3. 再删除 P1 的 `[pending]` → 期望 `marker: "idle"`

### 6. Clean 操作（破坏性）

⚠️ **此操作会修改文件！务必先复制。**

```bash
# 复制 fixture
cp tests/fixtures/TODO_clean.md /tmp/TODO_clean_test.md

# 执行 clean + all
PYTHONPATH=skills/cotodo python -m cotodo scan /tmp/TODO_clean_test.md --clean --all

# 验证文件已被修改
cat /tmp/TODO_clean_test.md
```

**验证要点：**
- JSON 输出仅包含 2 个话题："Keep this topic" 和 "Keep this too"
- `@delete` 话题已从文件中删除
- 文件内容干净（无多余空行）

### 7. Clean 默认模式（破坏性）

```bash
cp tests/fixtures/TODO_clean.md /tmp/TODO_clean_test2.md
PYTHONPATH=skills/cotodo python -m cotodo scan /tmp/TODO_clean_test2.md --clean
```

**期望结果：** `marker: "over"`，话题为 "Keep this topic"（含 over）。

### 8. 文件不存在

```bash
PYTHONPATH=skills/cotodo python -m cotodo scan /nonexistent/file.md --all
```

**期望结果：** JSON 中含 `error: "file not found"`，topics 为空列表。

## Fixture 设计原则

| 规则 | 原因 |
|------|------|
| 非破坏性测试直接使用原始文件 | 无复制开销，可重复运行 |
| 破坏性测试先复制到临时文件 | 保护 fixture 供下次使用 |
| 每个 fixture 聚焦一个主要关注点 | 便于定位失败原因 |
| `TODO_full.md` 覆盖所有边界情况 | 一个文件完成回归检查 |
| 话题标题包含场景描述 | 测试期望自文档化 |
