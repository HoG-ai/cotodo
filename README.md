# cotodo

**Collaborative TODO protocol for human-AI async workflows.**

A shared markdown file that enables asynchronous task collaboration between humans and AI agents. The human writes tasks, the agent processes them — no real-time chat required.

[中文文档](README.zh.md)

## How It Works

1. Human creates `TODO.md` with `##` topic headings
2. Human writes messages under topics, ending with `over`
3. Agent detects new messages, processes them, and replies
4. Async loop — no real-time chat needed

## Installation

```bash
# Option 1: pip
pip install cotodo

# Option 2: npx skills (agent skill ecosystem)
npx skills add github.com/HoG-ai/cotodo

# Option 3: curl
curl -sSL https://raw.githubusercontent.com/HoG-ai/cotodo/main/install.sh | bash
```

## TODO.md Protocol

```markdown
# Shared Task List

> `##` heading = one topic/task.
> User messages start with `User:`, end with `over` when ready.
> Delete old topics anytime. Add `@delete` after heading to auto-delete.
> Set `PAUSE: true` to pause the agent.

PAUSE:

## Fix login bug

User: Login fails when email has uppercase letters over
```

## Roadmap

- [x] Project scaffold + skill integration
- [ ] CLI commands (scan, mark, clear, reply, next, ...)
- [ ] PyPI publishing
- [ ] Documentation website

## License

MIT
