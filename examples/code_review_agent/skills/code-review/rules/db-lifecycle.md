# Database lifecycle rules

## Capability

`db-lifecycle` detects visible database connection creation without `close()`
and explicit transaction creation without visible `commit()` or `rollback()`
in the same Python hunk. Results contain deterministic remediation guidance.

## Blind spots

The rules do not prove context-manager, framework-managed, exception-path, or
cross-function cleanup. They do not understand every database driver or
transaction abstraction and should not replace integration tests.
