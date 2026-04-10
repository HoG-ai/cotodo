---
title: Overview
description: Async human-AI collaboration via shared TODO.md
---

# cotodo

**Async TODO protocol for human-AI collaboration.**

A shared Markdown file that enables humans and AI Agents to collaborate on tasks asynchronously. Humans write tasks, Agents process them — no real-time conversation needed.

## How It Works

1. Human creates `TODO.md` with `##` headings for topics
2. Writes messages under topics, adds `over` at the end
3. Agent detects new messages, processes and replies
4. Async loop — no real-time chat required

## Install

```bash
# Option 1: pip
pip install cotodo

# Option 2: npx skills (Agent skill ecosystem)
npx skills add github.com/HoG-ai/cotodo

# Option 3: curl
curl -sSL https://raw.githubusercontent.com/HoG-ai/cotodo/main/install.sh | bash
```

## TODO.md Example

```markdown
# Shared Task List

> `##` heading = one topic/task.
> User messages start with `User:`, end with `over` when done.
> Add `@delete` after heading for Agent to auto-delete the topic.
> Write `true` after `PAUSE:` to pause Agent.

PAUSE:

## Fix login bug

User: login fails when email has uppercase letters over
```
