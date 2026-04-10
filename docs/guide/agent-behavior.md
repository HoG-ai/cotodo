---
title: Agent Behavior
description: Agent behavior rules in cotodo collaboration workflow
---

Defines Agent behavior logic in the cotodo collaboration workflow. For file format and parsing rules, see [Protocol](./protocol).

## System Architecture

```
Human -> TODO.md <- cotodo scan (read-only) <- Agent
              ^
        Agent edits via terminal commands (sed/printf/cat)
```

- **Human**: Directly reads and writes TODO.md in the editor
- **Agent**: Gets structured state (JSON) via `cotodo scan`, edits the file via terminal commands
- **cotodo**: CLI tool with four scan mode combinations:

| Command | Behavior |
|---------|----------|
| `cotodo scan` | Read-only, returns highest priority topic + marker |
| `cotodo scan --clean` | Deletes @delete topics, then returns highest priority topic |
| `cotodo scan --all` | Read-only, returns all topics |
| `cotodo scan --clean --all` | Deletes @delete topics, then returns all topics |

## Agent Loop

Each iteration:

```
1. cotodo scan --clean → Get JSON (marker + highest priority topic), cleanup @delete topics
2. Act based on marker
3. Execute marker, edit TODO.md
4. Go to 1
```

Agent uses `scan --clean` in normal loops. `scan --all` is for debugging or when a global view is needed.

## Marker Reference

The `marker` field from `scan --clean` directly tells the Agent what to do:

| marker | Meaning | Agent Behavior |
|--------|---------|----------------|
| `"pause"` | PAUSE global stop | Immediately askQuestions to wait for user, do nothing else |
| `"processing"` | Has [processing] topic | Resume and complete the interrupted task |
| `"over"` | Has over topic | Process user's new message |
| `"pending"` | Has [pending] topic | Execute the planned task |
| `"idle"` | Nothing pending | askQuestions to wait for user |

**Notes**:
- @delete topics are removed in the `--clean` phase, not affecting marker selection
- Priority follows protocol masking rules: `processing` > `over` > `pending`
- `over` includes `queue_depth` indicating how many topics are queued

## Scenarios

### Scenario A: PAUSE

**Trigger**: scan returns `marker: "pause"`

**Behavior**:
1. Agent immediately calls `askQuestions` to wait for user
2. No topics are processed (over / pending / processing all deferred)

**Note**: PAUSE is the user's global switch for the Agent. User writes `PAUSE: true` in TODO.md to pause, clears the value to resume.

### Scenario B: @delete Cleanup

**Trigger**: `##` heading has `@delete` marker

**Behavior**: When Agent uses `cotodo scan --clean`, @delete topics are automatically deleted. All markers (over / pending / processing) within that topic disappear and are not processed.

**`scan` vs `scan --clean`**:
- `scan` (no flag): read-only, JSON shows `delete: true`, file unchanged
- `scan --clean`: deletes @delete topics first, then returns JSON for remaining topics. Deleted topics don't appear in results

**Note**: @delete is the user's signal to abandon that topic. Agent loop should always use `scan --clean` for one-step cleanup+scan.

### Scenario C: Resume [processing]

**Trigger**: scan returns `marker: "processing"`

**Behavior**:
1. Agent reads the topic's `context` (content from heading to [processing] line), restores context
2. Continues completing the previously interrupted task
3. Removes `[processing]` marker after completion, writes results

**Note**: `[processing]` means Agent started processing last round but didn't finish (possibly interrupted). This is the highest priority topic marker — must complete in-progress work first.

### Scenario D: Reply to User Message (over)

**Trigger**: scan returns `marker: "over"`

**Behavior**:
1. Change `over` to `[processing]` on that line (so user sees it's being processed)
2. Read topic `context` to understand user's message
3. Write `Agent:` reply in the topic
4. If it's an executable task: append `[pending]` at end of reply (plan but don't execute yet)
5. Remove `[processing]`, append blank line and `User:` placeholder
6. When multiple topics have over, process top-to-bottom one by one

**After reply state**:
- Pure reply (no task): topic returns to no-marker state
- Has task to execute: topic has `[pending]` marker, next round handles as Scenario F

### Scenario E: [processing] and over Coexist

**Trigger**: Agent is processing a topic ([processing]), user adds new `over` message in same topic

**scan behavior**: `processing` masks `over`, scan returns `marker: "processing"` (not `"over"`)

**Agent behavior**:
1. Current round: receives `processing`, continues completing in-progress task
2. Removes `[processing]` after completion
3. Next scan: finds new `over` in that topic, returns `marker: "over"`

**Note**: Consistency first. Cannot interrupt an in-progress task because user appended a message. User's new message is naturally picked up by the next scan round.

### Scenario F: Execute [pending] Task

**Trigger**: scan returns `marker: "pending"`

**Behavior**:
1. Change `[pending]` to `[processing]`
2. Execute the planned task in the topic
3. Remove `[processing]` after completion, write brief execution result

### Scenario G: [pending] and over Coexist

**Trigger**: Topic A has `[pending]`, Topic B (or same topic) has new `over`

**scan behavior**:
- Same topic: `over` masks `pending`, scan returns `marker: "over"`
- Different topics: `over` has higher priority than `pending`, scan still returns `marker: "over"`

**Agent behavior**:
1. Process `over` first (scan returns one highest priority topic per round, `over` > `pending`)
2. After all `over` are replied, scan returns `marker: "pending"`
3. Before executing, evaluate if `[pending]` plan needs adjustment (user's over may have revised the plan)
4. Plan unchanged: execute directly
5. Plan changed: update plan content, re-add `[pending]`, wait for next round

**Note**: User's over may revise existing plans. Align requirements before executing to avoid executing obsolete plans.

### Scenario H: Idle

**Trigger**: scan returns `marker: "idle"`

**Behavior**: Agent calls `askQuestions` to wait for user's next instruction.

## Marker Transition Summary

```
User finishes message, adds over
        |
        v
   over -> [processing]    Agent starts processing
        |
        +-> Pure reply -> Remove [processing], write Agent: reply + User:
        |
        +-> Has task -> Remove [processing], write Agent: plan [pending] + User:
                                |
                                v
                    [pending] -> [processing]    Agent starts executing
                                |
                                v
                        Remove [processing], write execution result
```
