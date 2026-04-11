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

Agent: Found the issue — email not normalized.

> **Summary** [pending]
> - [ ] auth.py#L42 add `.lower()`

User:

## Topic B @delete

User: old content
Agent: done
User:
```

## Topic Internal Structure

Each topic has two areas:

1. **Conversation area**: Append-only chronological messages (`User:` / `Agent:` alternating)
2. **Summary area** (optional): A blockquote section starting with `> **Summary**`, overwritten on each update

```markdown
## Topic Title

User: first message over

Agent: response here

User: follow-up over

Agent: updated analysis

> **Summary** [pending]
> - [ ] task 1
> - [ ] task 2

User:
```

The Summary area:
- Starts with a line matching `> **Summary**` (optionally followed by a marker like `[pending]`)
- Subsequent lines start with `>`
- Ends at the first non-`>` line (or end of topic)
- Semantics determined by content: if it contains TODO items (`- [ ] ...`), it's an execution plan; otherwise it's a conclusion
- Agent determines whether to add `[pending]` based on whether the plan needs execution

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
| `--take` | Atomically mark highest priority topic as `[processing]` and return it |

`--take` makes the scan operation non-read-only: it changes the topic's marker to `[processing]` before returning JSON, so the user can see the Agent has picked up the task. Typically combined with `--clean`: `cotodo scan --clean --take`.

### Default Output (highest priority)

```json
{"file": "TODO.md", "marker": "pause"}
```

```json
{"file": "TODO.md", "marker": "processing",
 "topic": {"title": "Fix bug", "line": 10, "end": 25, "marker_line": 15,
            "context": "User: ...", "summary": "- [ ] auth.py add .lower()"}}
```

```json
{"file": "TODO.md", "marker": "over",
 "topic": {"title": "Fix bug", "line": 10, "end": 25, "marker_line": 15,
            "context": "User: ...", "summary": null},
 "queue_depth": 3}
```

```json
{"file": "TODO.md", "marker": "pending",
 "topic": {"title": "Fix bug", "line": 10, "end": 25, "marker_line": 22,
            "context": "Agent: plan...", "summary": "- [ ] auth.py add .lower()"}}
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
| `summary` | string \| null | Content of the `> **Summary**` blockquote section (null if absent) |

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

## Reply Command

The `reply` command writes Agent's response back to a topic. It accepts JSON via stdin and performs atomic file update.

### Usage

```bash
cotodo reply <topic> [--compress] < input.json
```

| Flag | Effect |
|------|--------|
| (none) | Append message to conversation, overwrite Summary |
| `--compress` | Replace entire conversation area + Summary (context compression) |

### Input Format (JSON stdin)

```json
{
  "message": "Agent response text (appended to conversation with Agent: prefix)",
  "summary": "Summary content (overwrites existing) | null to keep current",
  "marker": "pending" | "processing" | null
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `message` | string | Yes | Reply text. Inserted with `Agent:` prefix |
| `summary` | string \| null | No | Overwrites `> **Summary**` section. `null` or omitted = keep existing |
| `marker` | string \| null | No | Set marker on Summary line: `"pending"`, `"processing"`, or `null` to clear |

### Reply Behavior

1. Parse input JSON from stdin
2. Locate the specified topic by title or line number
3. Append `Agent: {message}` to the conversation area (or replace if `--compress`)
4. If `summary` is present and non-null: overwrite the `> **Summary**` section (create if absent)
5. Set/clear marker on the `> **Summary**` line based on `marker` field
6. Remove `[processing]` (reply means processing is done)
7. Append `\nUser:\n` placeholder at the end
8. Atomic file write (`os.replace()` via temp file)

### `--compress` Mode

In compress mode, `message` contains the entire compressed conversation (including `User:` / `Agent:` lines). The command replaces all topic content (between `##` heading and next `##` or EOF) instead of appending.

Use case: when a user requests context compression, Agent summarizes the conversation history and uses `--compress` to replace verbose old content with a concise version.
