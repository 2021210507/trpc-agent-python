---
name: qa-tester
description: Execute and audit the DEV_SPEC quality gates for this repository's automatic code-review Agent under examples/code_review_agent. Runs focused pytest cases, the eight public diff fixtures, sandbox and Filter security tests, CLI/SQLite/report checks, offline evaluate.py gates, and optional container or real-LLM integrations while recording command evidence in QA_TEST_PROGRESS.md. Use when the user asks to "run QA", "QA test", "QA 测试", "执行测试", "跑测试", verify AC1-AC8, test a fixture or QA case ID, or "test and fix" the code-review Agent.
---

# QA Tester

Validate only the automatic code-review Agent implementation defined by `DEV_SPEC.md`.

## Authority

- “Run QA” authorizes test execution and read-only diagnosis. Do not edit product code.
- “Test and fix” authorizes minimal fixes with at most three diagnose/fix/retest rounds.
- Never stage, commit, install dependencies, start network services, or use a real model key without explicit authorization.
- Always preserve unrelated user changes.

## Evidence rules

1. Execute one QA case at a time.
2. Mark a case pass only from output produced in the current session.
3. Verify every expected assertion, not only the process exit code.
4. Record the exact command, exit code, test count or domain values, and duration when relevant.
5. Never pass a case by reading code, by citing another case, or because it “should work.”
6. Do not expose raw API keys, tokens, passwords, diff contents, environment values, or local absolute paths in progress notes.
7. A skipped test requires a documented optional prerequisite such as missing Docker or missing real-model Key. Missing implementation is not a skip.

## Files

| File | Purpose |
|---|---|
| `DEV_SPEC.md` | Normative requirements and AC1–AC8 |
| `QA_TEST_PLAN.md` | Case commands and expected evidence |
| `QA_TEST_PROGRESS.md` | One row per executed case |
| `references/test_patterns.md` | Evidence, report, database, security, and optional integration patterns |
| `scripts/qa_bootstrap.py` | Read-only environment/spec/readiness status |
| `scripts/qa_validate_notes.py` | Validate progress counters and execution evidence |

## 1. Select a target

- User supplies `A-01`, `C-08`, or a section: run only that scope.
- No scope: resume the first `🔧` case, otherwise the first `⬜` case.
- “Full QA”: run all non-optional cases in ID order, then optional cases when prerequisites exist.
- If the implementation schedule is partial, run cases whose DEV_SPEC task prerequisites are complete; leave later cases pending and report their prerequisite.

Read the selected row in `QA_TEST_PLAN.md` and the relevant DEV_SPEC section before execution.

## 2. Preflight

Use the repository virtual environment directly when it exists:

```powershell
.\.venv\Scripts\python.exe .github/skills/qa-tester/scripts/qa_bootstrap.py status
```

POSIX:

```bash
.venv/bin/python .github/skills/qa-tester/scripts/qa_bootstrap.py status
```

If there is no venv, use a Python `>=3.10` interpreter already available. Do not create an environment or install packages unless asked.

Confirm:

- `DEV_SPEC.md` has exactly chapters 1–7.
- auto-coder references are synced.
- `examples/code_review_agent/tests/{unit,integration,e2e,fixtures,support}/` exists and the project has no top-level test fixture directory.
- Docker and real-model Key availability only for optional section G.

## 3. Execute one case

Run the exact command from `QA_TEST_PLAN.md` or a narrower equivalent that proves every expected assertion.

Use:

- `tests/unit/` focused pytest for one deterministic module interface
- `tests/integration/` focused pytest for module/local-adapter collaboration and security boundaries
- `tests/e2e/` for CLI, evaluate, and parameterized public fixture flows
- `tests/fixtures/` only as input/expected data; a missing mandatory public fixture fails the case
- CLI commands plus JSON/Markdown/SQLite inspection for section E
- `evaluate.py --sandbox local` for the offline AC proxy gates
- Marked tests for optional container/real LLM integrations

Read [references/test_patterns.md](references/test_patterns.md) before report, database, redaction, Filter, or optional integration cases.

Do not combine multiple progress cases into one pass claim. A single suite command may produce evidence for the suite case H-01, but it does not automatically mark its component cases passed.

## 4. Judge the result

### Pass

All expected assertions were observed. Record:

```text
command="<command>", exit=0, pytest="N passed", key=value, duration_ms=N
```

At least two concrete evidence values are required in addition to the command.

### Fail

Record the failing assertion, exit code, and a short sanitized error excerpt. For a test-only request, diagnose the likely layer and stop or continue according to scope.

### Fix and retest

Only when authorized by “test and fix”:

1. Classify the failure: product bug, test bug, fixture problem, environment, or spec mismatch.
2. Make the smallest in-scope change.
3. Re-run the same case.
4. After three unsuccessful rounds, mark `❌` and report the remaining failure.
5. If shared code changed, re-run affected previously passed cases; do not silently retain stale pass evidence.

### Skip

Use `⏭️` only for:

- G-01 when Docker is unavailable
- G-02 when a real model Key is unavailable

Container/real skips do not block ordinary CI. Cube default-deny behavior is a deterministic security test and must not be skipped.

## 5. Record progress

Edit one row in `QA_TEST_PROGRESS.md` immediately after judging the case, then update summary counters in the same edit.

Statuses:

| Status | Meaning |
|---|---|
| `⬜` | Pending |
| `✅` | Passed with current-session evidence |
| `❌` | Failed |
| `🔧` | Fix applied; retest required |
| `⏭️` | Optional prerequisite unavailable |

After each section:

```powershell
.\.venv\Scripts\python.exe .github/skills/qa-tester/scripts/qa_validate_notes.py --section A
```

Do not proceed until the validator reports zero evidence/counter issues for completed rows.

## 6. AC interpretation

- AC1: all eight fixture cases generate JSON, Markdown, and database records.
- AC2: CI proves only the documented public proxy corpus; never claim hidden-sample acceptance.
- AC3: query the task bundle and all five table domains by task id.
- AC4: timeout/failure/output truncation become data and warnings, not review crashes.
- AC5: secrets are detected from controlled raw input while every output sink remains plaintext-free.
- AC6: the complete fake/local evaluate path is at most 120 seconds.
- AC7: `FilterAction.DENY` and `NEEDS_HUMAN_REVIEW` have zero sandbox side effects.
- AC8: canonical JSON contains all required sections and Markdown is rendered from it.

Warnings, suppressed candidates, and needs-human-review items do not count in findings P/R/F1.

## 7. Finish

Report:

- Cases passed, failed, skipped, and still pending
- Exact commands and aggregate counts
- AC coverage reached
- Sanitized failures and likely ownership
- Fixes made, if authorized

Never claim full acceptance while required cases remain pending or while only optional integrations ran.
