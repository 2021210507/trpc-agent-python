# Code Review Agent QA patterns

Use these patterns for the automatic code-review Agent only.

## Interpreter

Prefer the repository venv without shell activation:

```powershell
$py = ".\.venv\Scripts\python.exe"
& $py -m pytest examples/code_review_agent/tests/unit/test_config.py -q
```

POSIX equivalent:

```bash
py=.venv/bin/python
"$py" -m pytest examples/code_review_agent/tests/unit/test_config.py -q
```

Do not install missing dependencies during QA unless the user asks.

## Pytest evidence

Record:

- exact command
- exit code
- passed/failed/skipped count
- duration
- one domain assertion from output when available

Example:

```text
command=".\.venv\Scripts\python.exe -m pytest .../test_dedup.py -q", exit=0, pytest="7 passed", boundaries="0.50/0.80"
```

A suite pass does not replace focused evidence for another progress row.

## Fixture evidence

For each public fixture verify:

1. Expected finding/bucket/status
2. `review_report.json` exists and passes schema
3. `review_report.md` exists and matches canonical JSON statistics
4. SQLite task bundle contains task, sandbox run, Filter events as applicable, findings, and report
5. No known fixture secret occurs in report, database, captured logs, or sandbox summaries

Use only synthetic test credentials. Never paste them into `QA_TEST_PROGRESS.md`; record `plaintext_hits=0`.

## Canonical report checks

Required top-level evidence:

- `schema_version`
- `rule_pack_version`
- `config_digest`
- `input_sha256`
- `task_id`
- findings, needs-human-review, warnings, and suppressed count
- Filter summary
- sandbox summary
- metrics snapshot
- final conclusion

Verify Markdown is rendered from the same JSON object by comparing task id, severity distribution, bucket counts, and conclusion. Simulate a failed write in unit tests and verify no partial target remains.

## SQLite checks

Prefer repository tests through `ReviewStore.get_task_bundle(task_id)`. If direct inspection is required, use Python's `sqlite3` module and print only counts, status, rule/category enums, and hashes.

Never print evidence, stdout/stderr, Filter reasons, config values, or raw report JSON from a secret fixture.

## Redaction checks

Verify both sides:

```text
detected secret finding count > 0
plaintext hits across every output sink = 0
```

Cover:

- finding evidence and recommendation
- Filter reasons
- sandbox stdout/stderr
- exception messages
- JSON and Markdown
- SQLite bytes or decoded text columns
- captured logs
- Telemetry attributes

The detector must inspect controlled raw input before redaction. A report with no plaintext but also no secret finding is not a pass.

## Filter side-effect sentinel

For deny/review cases:

1. Request an unregistered script, invalid hash, escaping path, invalid argument, or over-budget run.
2. Use a sentinel file as the attempted side effect.
3. Assert Filter action.
4. Assert sandbox run count is zero.
5. Assert sentinel does not exist.
6. Assert the sanitized event is stored.

Do not run a genuinely destructive command for the sentinel.

## Path boundary

Use temporary directories to cover:

- `../` traversal
- absolute host path
- symlink/junction from repo input to an external temporary file
- file count, total bytes, or diff-line limit

Assert rejection occurs before target content is read or staged. Never use a real sensitive file as the external target.

## Runtime boundaries

- Container: assert default `network_mode=none`.
- Local: require explicit selection and a warnings entry.
- Cube: assert default Filter denial when runtime reports network access.
- Timeout/nonzero/truncated output: assert `cr_sandbox_run` and warnings, plus final report when possible.

## Evaluation

Run the public proxy gate with fake model and explicit local sandbox:

```powershell
.\.venv\Scripts\python.exe examples/code_review_agent/evaluate.py --sandbox local
```

Verify `eval_summary.json` contains:

- fixtures `8/8`
- high-severity recall `>=0.80`
- finding-level false-positive share `<=0.15`
- redaction detection rate `>=0.95`
- wall-clock time `<=120s`
- Precision, Recall, F1 as observational values
- Python, platform, runtime, schema/rule-pack/config digest

Default evaluation must not write the business `review.db`; use `--write-db` only in its dedicated case with a temporary database.

## Optional integrations

```powershell
.\.venv\Scripts\python.exe -m pytest examples/code_review_agent/tests/integration -q -m container
.\.venv\Scripts\python.exe -m pytest examples/code_review_agent/tests/integration -q -m real_llm
```

Skip only when the corresponding prerequisite is absent. Never reveal Key prefixes or values in notes.
