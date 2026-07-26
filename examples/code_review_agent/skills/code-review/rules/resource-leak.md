# Resource leak rules

## Capability

`resource-leak` detects visible `open(...)` and `ClientSession(...)` creation
without a matching visible close in the same hunk. It reports medium-confidence
candidates so downstream bucketing can require human review where appropriate.

## Blind spots

The rules cannot prove ownership transfer, context-manager behavior across
hunks, exception-path cleanup, factory wrappers, or interprocedural resource
lifecycle. They are intentionally conservative heuristics.
