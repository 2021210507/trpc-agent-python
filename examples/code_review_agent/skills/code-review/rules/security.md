# Security rules

## Capability

`security.*` detects changed Python uses of interpolated SQL f-strings,
`shell=True`, `eval`, `exec`, and `os.system`. The AST confirmation rule is
used only when a complete, syntax-valid Python file is available. Findings are
high or critical confidence-qualified deterministic results.

## Blind spots

The rules do not perform taint tracking, cross-function analysis, shell-command
semantic parsing, or validation of business authorization logic. Dynamic
imports and aliases outside the supported syntax can evade detection.
