---
name: cotodo
description: 'Shared TODO.md collaboration workflow. Async dialog-based collaboration between user and Agent via TODO.md: user adds topics/tasks, Agent loops reading and processing. Use when: multiple bugs or tasks, batch fixes, parallel collaboration, user mentions TODO or task list.'
---

# TODO Collaboration

## AI Behavior Rules

1. If project has no `TODO.md`, create one using the template below and add it to `.gitignore`
2. Edit `TODO.md` via **terminal commands** (sed/printf/cat), not VS Code diff (avoids conflicts with user editing simultaneously)
3. Continuously loop reading `TODO.md`, **re-read each iteration** (user may append content at any time)
4. Each iteration, first run `grep -in 'over\s*$\|@delete\s*$' TODO.md` to locate all pending lines; don't only read file tail
5. Each iteration check `PAUSE:` — if any visible character follows, immediately askQuestions to pause, do nothing else
6. Prioritize topics with `over` marker (case-insensitive, trailing whitespace OK); when multiple, process top-to-bottom one by one
7. When starting to process, change `over` at end of user message to `[processing]` (so user sees it's being processed); remove `[processing]` after reply is complete
8. Reply format: `Agent:` reply → append blank line and `User:` placeholder at end
9. When uncertain about user's message, reply with questions directly in the topic area; don't use askQuestions
10. `[pending]` task marker: When Agent replies with a plan, append `[pending]` at end, meaning "know how to do it but not executing yet". Rules:
    - Only keep `[pending]` at the end of the last Agent reply in a topic; remove old ones when adding new reply
    - Still append `User:` placeholder after reply (user may have feedback; incorporate and update plan, then re-add `[pending]`)
    - After all `over` messages are replied to, execute `[pending]` topics' actual tasks one by one
    - Remove `[pending]` after task execution, write brief result in the topic
11. When `##` heading ends with `@delete` (trailing whitespace OK), delete the entire topic section (from `##` to before next `##`)
12. When no pending messages remain, call askQuestions to wait for user instructions

## Init Template

```markdown
# Shared Task List

> `##` heading = one topic/task.
> User messages start with `User:`, end with `over` when done. Agent changes it to `[processing]` while processing.
> User can delete old topics and message history anytime. Add `@delete` after heading for Agent to auto-delete the topic.
> Write `true` after `PAUSE:` to pause Agent and bring up the dialog.

PAUSE:

## First topic

User: Describe your problem or task over
```
