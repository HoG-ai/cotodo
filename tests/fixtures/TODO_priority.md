# Priority Chain Test

> Tests action priority order: pause > resume > reply > execute > idle.
> This file has NO PAUSE, so priority starts from resume.

PAUSE:

## P1 - has pending (lowest active priority)

User: plan step 1
Agent: step 1 planned [pending]
User:

## P2 - has over (higher than pending)

User: please review this over

## P3 - has processing (highest active priority)

User: deploying now [processing]

## P4 - idle (no markers)

User: just notes
Agent: acknowledged
User:
