# cotodo

**人机异步协作的 TODO 协议。**

一个共享的 Markdown 文件，让人类和 AI Agent 异步协作任务。人写任务，Agent 处理——无需实时对话。

[English](README.md)

## 工作原理

1. 人类创建 `TODO.md`，用 `##` 标题划分话题
2. 在话题下写消息，写完末尾加 `over`
3. Agent 检测到新消息，处理并回复
4. 异步循环——不需要实时聊天

## 安装

```bash
# 方式1: pip
pip install cotodo

# 方式2: npx skills（Agent skill 生态）
npx skills add github.com/HoG-ai/cotodo

# 方式3: curl
curl -sSL https://raw.githubusercontent.com/HoG-ai/cotodo/main/install.sh | bash
```

## TODO.md 协议

```markdown
# 共享任务清单

> `##` 标题 = 一个话题/任务。
> 用户消息用 `User:` 开头，写完末尾加 `over`，Agent 处理时改为 `[pending...]`。
> 用户可随时删除旧话题。标题后加 `@delete` 可让 Agent 自动删除。
> `PAUSE:` 后写 `true` 可暂停 Agent。

PAUSE:

## 修复登录 bug

User: 邮箱有大写字母时登录失败 over
```

## 路线图

- [x] 项目框架 + skill 集成
- [ ] CLI 命令（scan, mark, clear, reply, next, ...）
- [ ] PyPI 发布
- [ ] 文档网站

## 许可证

MIT
