---
name: cotodo
description: '共享任务清单协作工作流。通过 TODO.md 实现用户与 Agent 的异步对话式协作：用户追加话题/任务，Agent 循环读取并处理。Use when: 收到多个 bug 或任务、批量修复、并行协作开发、用户提到 TODO 或任务清单。'
---

# TODO Collaboration

## AI 行为指令

1. 若项目无 `TODO.md`，用下方模板创建并加入 `.gitignore`
2. 编辑 `TODO.md` 用**终端命令**（sed/printf/cat），不走 VS Code diff（避免与用户同时编辑冲突）
3. 持续循环读 `TODO.md`，每次循环**重新读**（用户可能随时追加内容）
4. 每次循环先用 `grep -in 'over\s*$\|@delete\s*$' TODO.md` 定位所有待处理行；不要只读文件尾部
5. 每次循环检查 `PAUSE:`，后面有任何可见字符时立即 askQuestions 暂停，不做其他操作
6. 优先处理有 `over` 标记的话题（不区分大小写，末尾可有空格），多个时从上到下逐个处理
7. 开始处理时将用户消息末尾的 `over` 改为 `[processing]`（让用户看到正在处理），回复完成后删除 `[processing]`
8. 回复格式：`Agent:` 回复 → 末尾加空行和 `User:` 占位
9. 对用户消息有疑问时，直接在话题区回复提问，不用 askQuestions
10. `[pending]` 任务标记：Agent 回复方案时在末尾加 `[pending]`，表示"知道怎么做但暂不执行"。规则：
    - 永远只在话题内最后一条 Agent 回复末尾保留 `[pending]`，有新回复时删除旧的
    - 回复后仍加 `User:` 占位（用户可能有意见，有意见就综合后更新方案再加 `[pending]`）
    - 所有 `over` 消息回复完毕后，再逐个执行 `[pending]` 话题的实际任务
    - 任务执行完成后删除 `[pending]`，在话题里简要写执行结果
11. `##` 标题末尾有 `@delete` 标记时（末尾可有空格），删除该话题整段（从 `##` 到下一个 `##` 之前）
12. 没有待处理的消息时，调用 askQuestions 等待用户指令

## 初始化模板

```markdown
# 共享任务清单

> `##` 标题 = 一个话题/任务。
> 用户消息用 `User:` 开头，写完末尾加 `over`，Agent 处理时改为 `[processing]`。
> 用户可随时删除旧话题和消息记录。标题后加 `@delete` 可让 Agent 自动删除该话题。
> `PAUSE:` 后写 `true` 可暂停 Agent，调出对话框。

PAUSE:

## 第一个话题

User: 描述你的问题或任务 over
```
