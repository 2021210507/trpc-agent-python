# Async error rules

## Capability

`async-errors` detects `time.sleep` in a visible async function and visible
coroutine calls that are neither awaited nor scheduled. It reviews newly added
Python lines only and emits deterministic evidence with remediation guidance.

## Blind spots

The rules do not model control flow, decorators, aliases, callbacks, task
ownership, or coroutines passed between functions. A clean result is not proof
that every asynchronous failure path is handled.
