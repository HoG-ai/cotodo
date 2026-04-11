---
title: Agent Behavior
description: Agent behavior rules in cotodo collaboration workflow
---

Defines Agent behavior logic in the cotodo collaboration workflow. For file format and parsing rules, see [Protocol](./protocol).

## System Architecture

```
Human -> TODO.md <- cotodo scan    (read) <- Agent
              ^         cotodo reply (write)
              |
        atomic file operations
```

- **Human**: Directly reads and writes TODO.md in the editor
- **Agent**: Reads state via `cotodo scan`, writes back via `cotodo reply`
- **cotodo**: CLI tool, two core commands:

| Command | Behavior |
|---------|----------|
| `cotodo scan [--clean] [--all]` | Parse TODO.md, return JSON state |
| `cotodo scan --clean --take` | Clean + mark highest priority as [processing] + return |
| `cotodo reply <topic> [--compress]` | Write reply (stdin JSON), update conversation + Summary |

## Agent Loop

Each iteration:

```
1. cotodo scan --clean --take → Get JSON + mark topic [processing]
2. Work on the task based on marker + context + summary
3. cotodo reply <topic> → Write reply back, clears [processing]
4. Go to 1
```

- `scan --clean --take` atomically: cleanup @delete → mark highest priority → return JSON
- `reply` atomically: append conversation + overwrite Summary + manage markers + add User: placeholder
- `scan --all` is for debugging or when a global view is needed

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
1. Agent reads the topic's `context` and `summary`, restores context
2. Continues completing the previously interrupted task
3. Calls `cotodo reply` to write results

**Note**: `[processing]` means Agent started processing last round but didn't finish (possibly interrupted). This is the highest priority topic marker — must complete in-progress work first.

### Scenario D: Reply to User Message (over)

**Trigger**: scan returns `marker: "over"` (with `--take`, `over` is already changed to `[processing]`)

**Behavior**:
1. Read topic `context` to understand user's message, read `summary` for current plan/conclusion
2. Call `cotodo reply` with:
   - `message`: Agent's response to user
   - `summary`: updated plan/conclusion (if changed)
   - `marker`: `"pending"` if summary contains an execution plan; `null` otherwise
3. When multiple topics have over, `scan --take` returns the first; subsequent rounds handle the rest

**After reply state**:
- Pure reply (no task): topic in no-marker state, summary as conclusion
- Has task to execute: topic has `[pending]` on Summary, next round handles as Scenario F

### Scenario E: [processing] and over Coexist

**Trigger**: Agent is processing a topic ([processing]), user adds new `over` message in same topic

**scan behavior**: `processing` masks `over`, scan returns `marker: "processing"` (not `"over"`)

**Agent behavior**:
1. Current round: receives `processing`, continues completing in-progress task
2. Calls `cotodo reply` to write results
3. Next scan: finds new `over` in that topic, returns `marker: "over"`

**Note**: Consistency first. Cannot interrupt an in-progress task because user appended a message. User's new message is naturally picked up by the next scan round.

### Scenario F: Execute [pending] Task

**Trigger**: scan returns `marker: "pending"` (with `--take`, `[pending]` is changed to `[processing]`)

**Behavior**:
1. Read topic `summary` for the execution plan
2. Execute the planned task
3. Call `cotodo reply` with results and updated summary (mark completed items)

### Scenario G: [pending] and over Coexist

**Trigger**: Topic A has `[pending]`, Topic B (or same topic) has new `over`

**scan behavior**:
- Same topic: `over` masks `pending`, scan returns `marker: "over"`
- Different topics: `over` has higher priority than `pending`, scan still returns `marker: "over"`

**Agent behavior**:
1. Process `over` first (scan returns one highest priority topic per round, `over` > `pending`)
2. When processing `over` in a topic that had `[pending]`: remove `[pending]` first, reply, then decide whether to re-add
3. After all `over` are replied, scan returns `marker: "pending"`
4. Before executing, evaluate if `[pending]` plan needs adjustment (user's over may have revised the plan)

**Note**: User's over may revise existing plans. Align requirements before executing to avoid executing obsolete plans.

### Scenario H: Idle

**Trigger**: scan returns `marker: "idle"`

**Behavior**: Agent calls `askQuestions` to wait for user's next instruction.

## Marker Transition Summary

```
User finishes message, adds over
        |
        v
   scan --take: over -> [processing]    Agent picks up task
        |
        v
   Agent works, then calls reply:
        |
        +-> Pure reply    -> reply removes [processing], writes message + User:
        |
        +-> Has plan      -> reply removes [processing], writes message
        |                    + Summary [pending] + User:
        |
        v
   scan --take: [pending] -> [processing]    Agent picks up plan
        |
        v
   Agent executes, then calls reply:
        |
        v
   reply removes [processing], writes result + updated Summary + User:
```
