---
name: auto-coder
description: Implement the next task from this repository's DEV_SPEC.md for the automatic code-review Agent under examples/code_review_agent. Syncs the seven spec chapters, selects an A1-E2 schedule item, implements it test-first, validates its acceptance criteria, and updates progress without committing unless explicitly authorized. Use when the user asks for "auto code", "自动开发", "自动写代码", "auto dev", "一键开发", "autopilot", to continue the DEV_SPEC schedule, or to implement a specific task such as "auto code A3".
---

# Auto Coder

Implement one `DEV_SPEC.md` schedule item per cycle:

```text
Sync spec → select task → read required chapters → inspect code → implement + test → verify acceptance → update progress
```

Treat `DEV_SPEC.md` as the single source of truth. Generated files under `references/` are navigation aids only.

## Invocation

- No task ID: pick the first `[~]` task, otherwise the first `[ ]` task in chapter 6.
- Task ID supplied, such as `auto code B4`: implement that task.
- `--no-commit`: never offer to commit.
- Do not implement chapter 7 future work unless the user explicitly requests it and accepts the scope expansion.

Work autonomously unless a required decision would materially change the locked spec or requires new authority.

## 1. Sync the specification

Use the active Python interpreter:

```powershell
python .github/skills/auto-coder/scripts/sync_spec.py
```

If Python is unavailable, read `DEV_SPEC.md` directly. Never continue from stale generated references.

Read every cycle:

- `references/06-schedule.md`
- The target task row, including acceptance criteria and test method

Read as needed:

| Reference | Read when |
|---|---|
| `01-overview.md` | Confirming scope, locked decisions, or AC1–AC8 |
| `02-features.md` | Implementing domain behavior, inputs, rules, sandbox, storage, reports, or CLI |
| `03-tech-stack.md` | Selecting SDK APIs, Python compatibility, or dependencies |
| `04-testing.md` | Writing or running tests |
| `05-architecture.md` | Adding modules, changing pipeline stages, or crossing trust boundaries |
| `07-future.md` | Checking that a request is out of scope |

## 2. Check prerequisites

Before editing:

1. Read the target task and direct predecessors.
2. Inspect the actual repository; do not assume predecessor files exist because their markers changed.
3. Check `git status` and preserve unrelated user changes.
4. Locate the repository Python:
   - Windows: `.venv\Scripts\python.exe`
   - POSIX: `.venv/bin/python`
   - Otherwise use `python` only if it satisfies Python `>=3.10`.
5. Run the narrowest existing test that establishes the current baseline.

If a predecessor is genuinely absent and blocks the target, stop with concrete evidence. Do not silently implement multiple schedule tasks.

## 3. Plan the task

Extract:

- Files to create or modify
- Public inputs and outputs
- Trust boundaries crossed
- Acceptance assertions
- Required unit, integration, or fixture tests

Keep the plan scoped to one task. A normal implementation may include small supporting changes required to make that task testable.

## 4. Implement test-first

Prefer:

```text
failing focused test → minimal implementation → focused test passes → regression test
```

Apply these repository rules.

### Project boundary

- Deliver under `examples/code_review_agent/` unless the task explicitly changes shared SDK code.
- Follow the directory tree in DEV_SPEC §5.2.
- Support Python `>=3.10`; do not use Python 3.12-only syntax.
- Keep `skills/code-review/scripts/` on the Python standard library only.
- Reuse tRPC-Agent SDK Skills, workspace runtimes, Filter chain, Telemetry, Agent, Runner, and SQLAlchemy dependencies. Do not recreate SDK framework mechanisms.

### Single-source rules

- Keep diff parsing, deterministic rules, and secret patterns in `skills/code-review/scripts/lib/`.
- Both CLI/pipeline and `LlmAgent + SkillToolSet` must use the same `ReviewPipeline`.
- Both entry points must share the same execution manifest, Filter, sandbox, storage, and report model.
- Do not duplicate rule logic under `codereview/`.

### Input semantics

- Treat tracked repo changes and diff patches as changed-line review.
- Treat `--files` as an explicit full-file snapshot scan: `status=snapshot`, `review_scope=full_file`, and every line is in scope. Do not claim historical-issue filtering for this mode.
- Let each fixture preserve its declared payload type; do not convert a diff fixture into a full-file snapshot.
- Represent added/snapshot hunks with old `0,0` and deleted hunks with new `0,0`; never emit missing/`None` hunk coordinates.
- Populate `old_to_new_line_map` only for unchanged context lines.
- Run ordinary code rules on the new side only. A deleted-side secret may use its real old line with `line_side=old`; never invent line 0 or a nearby new line.
- Include source kind and per-file review scope in canonical report input summaries.

### Execution governance

- Accept only `script_id + structured_args`.
- Resolve commands from `skills/code-review/scripts/manifest.json`.
- Never introduce `shell=True`, arbitrary command execution, online dependency installation, writable host-repository mounts, or silent local fallback.
- Run Filter checks before sandbox execution. `DENY` and `NEEDS_HUMAN_REVIEW` must not execute.
- Keep the locked budgets: 10 runs, 30 seconds per run, 90 seconds sandbox total, 110 seconds review deadline, 1 MiB per run output, 2 MiB per review.

### Sensitive-data boundary

- Let the secrets rule inspect original input only inside controlled host task memory/temp storage and the isolated workspace.
- Never log raw diff lines or environment-variable values.
- Redact sandbox evidence/output first, redact all host fields again, then scan the complete JSON/Markdown/database payload before persistence.
- Never send raw diff, evidence, stdout/stderr, Filter reasons, or secrets to an LLM or Telemetry.
- Clean the task workspace in `finally`.

### Findings and reports

- Preserve the finding contract and `(file, line, category)` dedup key.
- Keep deterministic ordering and non-overlapping buckets:
  - findings: `0.80 <= confidence <= 1.00`
  - needs human review: `0.50 <= confidence < 0.80`
  - suppressed: `<0.50`
  - warnings: runtime/governance problems only
- Do not give confidence a severity-based floor.
- Generate canonical JSON first; validate schema, redact, and write atomically.
- Render Markdown only from canonical JSON.
- LLM enhancement may change only recommendation, summary, and review guidance. It may not alter finding identity, rule, severity, confidence, bucket, or deduplication.

### Testing

- Put all test code, support code, and test data under `examples/code_review_agent/tests/`; do not create a top-level `fixtures/`.
- Put deterministic single-module tests in `tests/unit/`, module/adapter collaboration tests in `tests/integration/`, and complete CLI/evaluate flows in `tests/e2e/`.
- Keep fixture data under `tests/fixtures/` and shared fakes/builders/assertions under `tests/support/`. Fixtures contain data, not executable tests.
- Unit tests must not require Docker, network, or a real model key. Missing mandatory fixture data is a failure, not a skip.
- Inject fake workspace/model dependencies through public constructors or interfaces.
- Mark real integrations with `container` or `real_llm`.
- Assert observable outputs: CLI exit codes, JSON/MD content, database rows, sandbox run records, Filter events, metrics, and absence of plaintext secrets.

## 5. Validate

Run the test named in the task row, then relevant regressions. Use the repository interpreter, for example:

```powershell
.\.venv\Scripts\python.exe -m pytest examples/code_review_agent/tests/unit/test_diff_parser.py -q
```

For a completed vertical slice, also run:

```powershell
.\.venv\Scripts\python.exe -m pytest examples/code_review_agent/tests -q -m "not container and not real_llm"
```

Allow at most three focused diagnose/fix/retest rounds. Do not weaken assertions, hide failures with broad exception handling, or mark a task complete because a test was skipped.

Before completion, verify:

- Every acceptance clause in the target task has direct evidence.
- No out-of-scope future feature was added.
- No plaintext test secret appears in report, database, captured logs, or sandbox summaries.
- No unrelated file was overwritten.

## 6. Update progress

Only after acceptance passes:

1. Change the target task marker in `DEV_SPEC.md` from `[ ]`/`[~]` to `[x]`.
2. Do not rewrite its acceptance criteria.
3. Re-sync:

```powershell
python .github/skills/auto-coder/scripts/sync_spec.py --force
```

If blocked or tests still fail, leave the task `[~]` and report the exact blocker.

## 7. Hand off

Report:

- Task ID and outcome
- Files changed
- Tests run with pass/fail/skip counts
- Remaining warnings or environment-dependent tests
- Next pending task

Do not stage or commit unless the user explicitly requests it. If requested, commit only the completed task and its regenerated reference files.
