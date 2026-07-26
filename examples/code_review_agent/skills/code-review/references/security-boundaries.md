# Security boundaries

## Trust domains

Raw diffs and file snapshots are untrusted. They may exist only in controlled
host memory, a task temporary directory, and the isolated workspace. They must
not enter logs, telemetry, LLM prompts, reports, or persistent storage. The
only allowed sandbox input for this Skill is `work/inputs/diff.json`.

## Execution allowlist

The host accepts only `script_id` plus manifest-defined structured arguments.
It verifies the manifest entrypoint and SHA-256 before execution, applies the
real Filter chain first, and short-circuits `DENY` and
`NEEDS_HUMAN_REVIEW` decisions. Shell strings, dynamic downloads, dependency
installation, writable host-repository mounts, and arbitrary network access
are prohibited.

## Budgets and environment

Every script has a 30-second limit and at most 1 MiB of output. A review is
limited to ten runs, 90 sandbox seconds, 110 total seconds, and 2 MiB combined
output. Network policy is deny. The host constructs an environment from an
allowlist; API keys, tokens, passwords, and inherited environment values are
never passed through.

## Output and failure handling

The sandbox redacts findings before writing output. The host redacts again and
performs a complete exit scan before persistence. Timeouts, nonzero exits,
truncation, Filter decisions, and cleanup failures become sanitized run records
and warnings. A sandbox failure never falls back to host-side rule execution.
