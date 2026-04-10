# Test Shared Task List

> This is a test fixture covering all protocol scenarios.
> Used for manual and automated testing.

PAUSE:

## T1 - over basic

User: fix the login bug over

## T2 - over case insensitive

User: uppercase test OVER

## T3 - over trailing whitespace

User: trailing spaces over   

## T4 - over NOT at end

User: the game is over now
User:

## T5 - over in code block (ignored)

```
User: this over should be ignored
```

User: normal text here
User:

## T6 - over in inline code (ignored)

User: check `over` usage
User:

## T7 - over in table row (ignored)

| Command | Description |
|---------|-------------|
| over    | should skip |

User:

## T8 - processing replaces over

User: fix color [processing]

## T9 - processing masks earlier over

User: first message over
Agent: got it, working on it
User: second message [processing]

## T10 - pending basic

User: fix the button style
Agent: I will fix the button style [pending]
User:

## T11 - pending masked by over

User: original request
Agent: my previous plan [pending]
User: new instruction over

## T12 - delete topic @delete

User: old content to be removed
Agent: done
User:

## T13 - multiple overs (last wins)

User: first message over
Agent: reply to first
User: second message over
Agent: reply to second
User: third and last over

## T14 - idle (no markers)

User: just a note without any marker
Agent: acknowledged
User:

## T15 - mixed markers processing wins all

User: msg over
Agent: plan [pending]
User: urgent [processing]

## T16 - empty topic (no content)

## T17 - context extraction multi-line

User: line 1
Agent: response 1
User: line 2
Agent: response 2
User: line 3 over
