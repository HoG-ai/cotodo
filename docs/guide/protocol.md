---
title: Protocol Specification
description: TODO.md file format, markers, and parsing rules
---

This document defines the TODO.md file format, markers, and parsing rules.

## File Structure

A TODO.md file consists of:

1. **Header**: Title (`#`) + description block (blockquote `>`)
2. **Global controls**: `PAUSE:` directive
3. **Topics**: Each starts with `##` heading, contains messages and replies

```markdown
# Shared Task List

> Description of the protocol rules...

PAUSE:

## Topic A

User: fix the login bug over

## Topic B @delete

User: old content
Agent: done
User:
```

## Markers

| Marker | Location | Match Rule | Meaning |
|--------|----------|------------|---------|
| `over` | End of line | Case-insensitive, trailing whitespace OK. Regex: `/over\s*$/i` | User message is complete, ready for Agent to process |
| `[processing]` | Replaces `over` | Exact match (in non-code context) | Agent is actively processing this message |
| `[pending]` | End of Agent reply | Exact match (in non-code context) | Agent has a plan but hasn't executed yet |
| `@delete` | End of `##` heading | Trailing whitespace OK. Regex: `/@delete\s*$/` | Topic should be deleted by Agent |
| `PAUSE:` | Standalone line (top level) | Any visible char after `:` = paused; whitespace-only = not paused | Global pause/resume Agent processing |
| `User:` | Start of line | Half-width colon | User message prefix |

### Matching Details

**`over`**: Must be the last visible token on the line. Only matched outside code blocks (` ``` `) and inline code (`` ` ``). Table rows (`|...|`) are excluded.

```
User: fix the bug over       ← matches (trailing space OK)
User: fix the bug Over       ← matches (case-insensitive)
User: fix the bug OVER       ← matches
User: the game is over now   ← does NOT match ("now" after "over")
```

**`[processing]`**: Replaces `over` when Agent starts processing a message, or replaces `[pending]` when Agent starts executing a planned task. Only one `[processing]` should exist globally at any time. Removed after the operation is complete.

**`[pending]`**: Only the last Agent reply in a topic should have `[pending]`. Old ones are removed when a new reply is added.

**`@delete`**: Must be at the end of a `##` heading line. The entire topic section (from `##` to before next `##` or EOF) is deleted.

**`PAUSE:`**: Evaluated each iteration. Any visible character after the colon means paused. Empty or whitespace-only means not paused.

```
PAUSE: true     ← paused
PAUSE: 1        ← paused
PAUSE: stop     ← paused
PAUSE:          ← NOT paused
PAUSE:          ← NOT paused (whitespace only)
```

## Scan Output Format

The `scan` command parses TODO.md and returns JSON. It supports two output modes and an optional cleanup flag.

### Flags

| Flag | Effect |
|------|--------|
| (none) | Read-only, return highest priority topic with marker |
| `--all` | Read-only, return all topics |
| `--clean` | Delete `@delete` topics before returning results |
| `--clean --all` | Delete `@delete` topics, then return all remaining topics |

### Default Output (highest priority)

```json
{"file": "TODO.md", "marker": "pause"}
```

```json
{"file": "TODO.md", "marker": "processing",
 "topic": {"title": "Fix bug", "line": 10, "end": 25, "marker_line": 15, "context": "User: ..."}}
```

```json
{"file": "TODO.md", "marker": "over",
 "topic": {"title": "Fix bug", "line": 10, "end": 25, "marker_line": 15, "context": "User: ..."},
 "queue_depth": 3}
```

```json
{"file": "TODO.md", "marker": "pending",
 "topic": {"title": "Fix bug", "line": 10, "end": 25, "marker_line": 22, "context": "Agent: plan..."}}
```

```json
{"file": "TODO.md", "marker": "idle"}
```

### Marker Priority

| Priority | Marker | Condition |
|----------|--------|-----------|
| 1 | `pause` | `PAUSE:` has visible value |
| 2 | `processing` | Topic has `[processing]` |
| 3 | `over` | Topic has `over` |
| 4 | `pending` | Topic has `[pending]` |
| 5 | `idle` | None of the above |

### `--all` Output (all topics)

```json
{
  "file": "TODO.md",
  "paused": false,
  "topics": [
    {
      "title": "Fix login bug",
      "line": 10,
      "end": 25,
      "delete": false,
      "over": 15,
      "processing": null,
      "pending": null,
      "context": "User: email with uppercase fails\nUser: also check special chars"
    }
  ]
}
```

### Topic Fields (`--all` mode)

| Field | Type | Description |
|-------|------|-------------|
| `title` | string | Heading text (without `@delete` marker) |
| `line` | int | Heading line number (1-based) |
| `end` | int | Last line of the topic section |
| `delete` | bool | Whether `@delete` marker is present |
| `over` | int \| null | Line number of last `over` (masked to null if `[processing]` exists) |
| `processing` | int \| null | Line number of `[processing]` marker |
| `pending` | int \| null | Line number of `[pending]` marker (masked to null if `over` or `[processing]` exists) |
| `context` | string \| null | Text from first non-blank line after heading to active marker |

### Normalization Rules

- **Priority masking**: `[processing]` > `over` > `[pending]` — higher priority marker masks lower ones to `null` in output
- **Multiple `over`**: Only the last one per topic is reported; earlier ones are ignored in JSON (file unchanged)
- **Context extraction**: follows same priority; context spans from first non-blank line after `##` heading to the marker line (inclusive, but marker text stripped)
- **No context for**: `@delete` topics, topics with no markers

### Parsing Rules

1. Line numbers are **1-based** (consistent with grep/sed)
2. Code blocks (` ``` `) are skipped — markers inside code blocks are ignored
3. Inline code (`` `...` ``) content is ignored
4. Table rows (`| ... |`) are excluded from marker detection
5. Each topic spans from its `##` heading to before the next `##` or EOF
6. Content before the first `##` is the header area (contains `PAUSE:`)

## Processing Rules

### `--clean` Behavior

When `--clean` is specified:
1. Parse the entire file
2. Identify topics with `@delete` marker
3. Remove those topic sections from the file content
4. Write back atomically (`os.replace()` via temp file)
5. Return results excluding deleted topics

If no `@delete` topics exist, no file write occurs (pure read-only).

### `[processing]` Dual Purpose

`[processing]` replaces both `over` and `[pending]`:

- **New message**: `over` → `[processing]` (Agent starts processing user message)
- **Execute task**: `[pending]` → `[processing]` (Agent starts executing planned task)

At any time, there should be at most one `[processing]` globally.

### Multiple `over` in Same Topic

When a user adds multiple messages with `over` in the same topic, only the **last one** is canonical:

```markdown
## Topic
User: fix button
User: also fix color
User: and font [processing]  ← last over → [processing]
User:
```

Agent's context includes all messages above (they're part of the topic content).

### Priority Order

1. `[processing]` — continue processing (Agent was interrupted or resumed)
2. `over` — new user message to process
3. `[pending]` — planned task to execute
4. idle — nothing to do

### Context Scope

Agent context = topic heading → active marker line (inclusive, marker text stripped). Content **below** the marker is excluded (may contain user's post-submission additions for the next round).
