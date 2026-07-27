# QA test plan — Automatic Code Review Agent

> Normative source: `DEV_SPEC.md`
>
> Scope: `examples/code_review_agent/`
>
> Default QA path: Python `>=3.10`, fake model, explicit local sandbox, no network, no real API Key.
>
> A case passes only with current-session command evidence. Optional container and real-LLM cases may skip when prerequisites are unavailable.
>
> Test layout: deterministic modules in `tests/unit/`, module/adapter collaboration in `tests/integration/`, complete flows in `tests/e2e/`, and data only in `tests/fixtures/`.

## A. Specification and readiness

| ID | DEV_SPEC gate | Command | Required evidence |
|---|---|---|---|
| A-01 | Seven-chapter source and generated references | `.\.venv\Scripts\python.exe .github/skills/auto-coder/scripts/sync_spec.py --force` then `.\.venv\Scripts\python.exe .github/skills/qa-tester/scripts/qa_bootstrap.py check-spec` | exit=0; chapters=7; references=7; synced hash matches |
| A-02 | Python and dependency readiness | `.\.venv\Scripts\python.exe .github/skills/qa-tester/scripts/qa_bootstrap.py status` | Python >=3.10; DEV_SPEC present; venv/interpreter and Docker availability reported; test_layers_valid=true; top_level_fixtures_exists=false |
| A-03 | A1 layered skeleton and test discovery | `.\.venv\Scripts\python.exe -m pytest examples/code_review_agent/tests --collect-only -q` | exit=0; tests collected from unit; integration/e2e/fixtures/support directories exist; no import error |
| A-04 | A1 ReviewConfig and report schema | `.\.venv\Scripts\python.exe -m pytest examples/code_review_agent/tests/unit/test_config.py -q` | input/timeout/output defaults, stable config_digest, schema load all pass |

## B. Deterministic modules

| ID | DEV_SPEC gate | Command | Required evidence |
|---|---|---|---|
| B-01 | A2 ChangeSet/diff boundaries | `.\.venv\Scripts\python.exe -m pytest examples/code_review_agent/tests/unit/test_diff_parser.py -q` | rename/binary/CRLF/no-newline/deleted/added, line mapping, input hash pass |
| B-02 | A8 input and staging boundary | `.\.venv\Scripts\python.exe -m pytest examples/code_review_agent/tests/integration/test_inputs.py -q` | four-way exclusivity, untracked text, traversal/symlink/size rejection pass |
| B-03 | A3 detect-then-redact | `.\.venv\Scripts\python.exe -m pytest examples/code_review_agent/tests/unit/test_redaction.py -q` | secret detection >=95%; benign set; all output fields plaintext-free |
| B-04 | A4 security rules and literal scope | `.\.venv\Scripts\python.exe -m pytest examples/code_review_agent/tests/unit/test_rules.py -q -k "security or secret"` | dangerous APIs detected; comment/string API mentions ignored; real-format string secret detected |
| B-05 | A5 async/resource rules | `.\.venv\Scripts\python.exe -m pytest examples/code_review_agent/tests/unit/test_rules.py -q -k "async or resource"` | async blocking/unawaited and resource lifecycle positive/negative cases pass |
| B-06 | A6 DB lifecycle/missing tests | `.\.venv\Scripts\python.exe -m pytest examples/code_review_agent/tests/unit/test_rules.py -q -k "db or missing"` | DB cases pass; missing-tests never enters high-confidence findings |
| B-07 | A7 changed-line AST | `.\.venv\Scripts\python.exe -m pytest examples/code_review_agent/tests/unit/test_rules_ast.py -q` | historical issue ignored; changed issue detected; added file AST; broken hunk fallback pass |
| B-08 | B2 stable dedup/buckets | `.\.venv\Scripts\python.exe -m pytest examples/code_review_agent/tests/unit/test_dedup.py -q` | triple-key dedup, stable order, also_matched, 0.50/0.80 boundaries pass |
| B-09 | B1 five-table store | `.\.venv\Scripts\python.exe -m pytest examples/code_review_agent/tests/integration/test_store.py -q` | CRUD, indexes/version fields, idempotent init, task bundle pass |
| B-10 | B4 canonical reports | `.\.venv\Scripts\python.exe -m pytest examples/code_review_agent/tests/integration/test_report.py -q` | schema, JSON/MD consistency, stable bytes, atomic write, leak blocking pass |
| B-11 | B3 metrics/Telemetry | `.\.venv\Scripts\python.exe -m pytest examples/code_review_agent/tests/unit/test_metrics.py -q` | immutable snapshot, bucket/filter counts, span allowlist pass |

## C. Paired public fixtures (8 smoke + 8 realistic)

| ID | Fixture | Command | Required evidence |
|---|---|---|---|
| C-01 | `01_clean` | `.\.venv\Scripts\python.exe -m pytest examples/code_review_agent/tests/e2e/test_fixtures_e2e.py -q -k 01_clean` | zero findings; JSON+MD+DB task bundle |
| C-02 | `02_security` | `.\.venv\Scripts\python.exe -m pytest examples/code_review_agent/tests/e2e/test_fixtures_e2e.py -q -k 02_security` | at least two high/critical security findings |
| C-03 | `03_async_leak` | `.\.venv\Scripts\python.exe -m pytest examples/code_review_agent/tests/e2e/test_fixtures_e2e.py -q -k 03_async_leak` | async-errors and resource-leak findings |
| C-04 | `04_db_lifecycle` | `.\.venv\Scripts\python.exe -m pytest examples/code_review_agent/tests/e2e/test_fixtures_e2e.py -q -k 04_db_lifecycle` | DB lifecycle finding |
| C-05 | `05_missing_tests` | `.\.venv\Scripts\python.exe -m pytest examples/code_review_agent/tests/e2e/test_fixtures_e2e.py -q -k 05_missing_tests` | missing-tests in needs-human-review, not findings |
| C-06 | `06_duplicate_finding` | `.\.venv\Scripts\python.exe -m pytest examples/code_review_agent/tests/e2e/test_fixtures_e2e.py -q -k 06_duplicate_finding` | one deduplicated result and nonempty also_matched |
| C-07 | `07_sandbox_failure` | `.\.venv\Scripts\python.exe -m pytest examples/code_review_agent/tests/e2e/test_fixtures_e2e.py -q -k 07_sandbox_failure` | completed_with_warnings; sandbox record; report still generated |
| C-08 | `08_secret_redaction` | `.\.venv\Scripts\python.exe -m pytest examples/code_review_agent/tests/e2e/test_fixtures_e2e.py -q -k 08_secret_redaction` | real-format secrets detected; placeholder reduced; plaintext_hits=0 in reports/DB/logs/runs |
| C-09 | `01_clean_realistic` | `.\.venv\Scripts\python.exe -m pytest examples/code_review_agent/tests/e2e/test_fixtures_e2e.py -q -k 01_clean_realistic` | 60–150 added code lines across multiple files; safe decoys; zero findings |
| C-10 | `02_security_realistic` | `.\.venv\Scripts\python.exe -m pytest examples/code_review_agent/tests/e2e/test_fixtures_e2e.py -q -k 02_security_realistic` | safe SQL/subprocess decoys ignored; at least two high-risk security findings |
| C-11 | `03_async_leak_realistic` | `.\.venv\Scripts\python.exe -m pytest examples/code_review_agent/tests/e2e/test_fixtures_e2e.py -q -k 03_async_leak_realistic` | safe async/resource patterns coexist with async-errors and resource-leak findings |
| C-12 | `04_db_lifecycle_realistic` | `.\.venv\Scripts\python.exe -m pytest examples/code_review_agent/tests/e2e/test_fixtures_e2e.py -q -k 04_db_lifecycle_realistic` | managed DB patterns ignored; connection and transaction lifecycle findings retained |
| C-13 | `05_missing_tests_realistic` | `.\.venv\Scripts\python.exe -m pytest examples/code_review_agent/tests/e2e/test_fixtures_e2e.py -q -k 05_missing_tests_realistic` | realistic production change without matching tests remains human-review only |
| C-14 | `06_duplicate_finding_realistic` | `.\.venv\Scripts\python.exe -m pytest examples/code_review_agent/tests/e2e/test_fixtures_e2e.py -q -k 06_duplicate_finding_realistic` | one same-line security result after dedup; also_matched remains nonempty |
| C-15 | `07_sandbox_failure_realistic` | `.\.venv\Scripts\python.exe -m pytest examples/code_review_agent/tests/e2e/test_fixtures_e2e.py -q -k 07_sandbox_failure_realistic` | realistic payload still yields completed_with_warnings and persisted failed run |
| C-16 | `08_secret_redaction_realistic` | `.\.venv\Scripts\python.exe -m pytest examples/code_review_agent/tests/e2e/test_fixtures_e2e.py -q -k 08_secret_redaction_realistic` | real-format synthetic secrets detected among benign decoys; plaintext_hits=0 in all sinks |

Every C case must produce canonical JSON, Markdown, and a queryable database record.

## D. Sandbox and governance security

| ID | DEV_SPEC gate | Command | Required evidence |
|---|---|---|---|
| D-01 | Execution manifest integrity | `.\.venv\Scripts\python.exe -m pytest examples/code_review_agent/tests/integration/test_skill_scripts.py -q -k manifest` | required fields, entrypoint realpath and SHA-256 pass |
| D-02 | Filter short-circuit | `.\.venv\Scripts\python.exe -m pytest examples/code_review_agent/tests/integration/test_governance.py -q -k "deny or human or sentinel"` | non-ALLOW actions; sandbox_runs=0; sentinel absent; event stored |
| D-03 | Path and input escape | `.\.venv\Scripts\python.exe -m pytest examples/code_review_agent/tests/integration/test_inputs.py -q -k "traversal or symlink or junction or limit"` | rejection before read/stage; sanitized warning |
| D-04 | Environment allowlist | `.\.venv\Scripts\python.exe -m pytest examples/code_review_agent/tests/integration/test_sandbox_safety.py -q -k environment` | canary absent from sandbox and all sinks |
| D-05 | Timeout as data | `.\.venv\Scripts\python.exe -m pytest examples/code_review_agent/tests/integration/test_sandbox_safety.py -q -k timeout` | timed_out=true; run row and warning; review does not crash |
| D-06 | Output limits | `.\.venv\Scripts\python.exe -m pytest examples/code_review_agent/tests/integration/test_sandbox_safety.py -q -k "output or trunc"` | per-run/review limits, truncated flag, sanitized summary |
| D-07 | Runtime network policy | `.\.venv\Scripts\python.exe -m pytest examples/code_review_agent/tests/integration/test_governance.py -q -k "network or cube or local or container"` | cube default deny; local warning; container network none |
| D-08 | All-sink redaction | `.\.venv\Scripts\python.exe -m pytest examples/code_review_agent/tests/integration/test_pipeline.py -q -k "secret or redact or plaintext"` | finding exists; plaintext_hits=0 across JSON/MD/DB/logs/Telemetry/sandbox/Filter |

## E. CLI, persistence, and failure semantics

| ID | DEV_SPEC gate | Command | Required evidence |
|---|---|---|---|
| E-01 | Idempotent database initialization | `.\.venv\Scripts\python.exe -m pytest examples/code_review_agent/tests/e2e/test_cli.py -q -k init_db` | two initializations exit=0; schema intact |
| E-02 | Zero-Key local dry-run | `.\.venv\Scripts\python.exe -m pytest examples/code_review_agent/tests/e2e/test_cli.py -q -k dry_run` | fake/local path succeeds; JSON+MD created; no Key required |
| E-03 | Show/list task bundle | `.\.venv\Scripts\python.exe -m pytest examples/code_review_agent/tests/e2e/test_cli.py -q -k "show or list"` | review task appears; show returns runs/events/findings/report |
| E-04 | Alternate SQL URL | `.\.venv\Scripts\python.exe -m pytest examples/code_review_agent/tests/e2e/test_cli.py -q -k db_url` | temporary SQLite URL used; business review.db untouched |
| E-05 | Exit codes | `.\.venv\Scripts\python.exe -m pytest examples/code_review_agent/tests/e2e/test_cli.py -q -k "exit or fail_on_severity"` | review 0/1/2 semantics and threshold behavior pass |
| E-06 | Partial failure continues | `.\.venv\Scripts\python.exe -m pytest examples/code_review_agent/tests/integration/test_pipeline.py -q -k "failure or warning or cleanup"` | noncritical failures become warnings; critical failures become failed; cleanup failure sanitized |

## F. Offline evaluation gates

| ID | DEV_SPEC gate | Command | Required evidence |
|---|---|---|---|
| F-01 | Public corpus and 8 fixtures | `.\.venv\Scripts\python.exe examples/code_review_agent/evaluate.py --sandbox local` | exit=0; fixtures=8/8; eval_summary.json exists |
| F-02 | AC2 public proxy | `.\.venv\Scripts\python.exe -m pytest examples/code_review_agent/tests/e2e/test_evaluate.py -q -k metrics` | high-risk recall >=0.80; finding-level FP share <=0.15; P/R/F1 present |
| F-03 | AC5 redaction rate | `.\.venv\Scripts\python.exe -m pytest examples/code_review_agent/tests/e2e/test_evaluate.py -q -k redact` | redaction detection rate >=0.95; plaintext_hits=0 |
| F-04 | AC6 wall-clock budget | `.\.venv\Scripts\python.exe -m pytest examples/code_review_agent/tests/e2e/test_evaluate.py -q -k duration` | complete fake/local flow <=120s |
| F-05 | Summary and optional history | `.\.venv\Scripts\python.exe -m pytest examples/code_review_agent/tests/e2e/test_evaluate.py -q -k "summary or write_db"` | environment/version digests recorded; default no DB write; explicit temporary history works |

## G. Optional integrations

| ID | Prerequisite | Command | Required evidence |
|---|---|---|---|
| G-01 | Docker available | `.\.venv\Scripts\python.exe -m pytest examples/code_review_agent/tests/integration -q -m container` | real container executes registered scripts; network_mode=none; no host fallback |
| G-02 | Explicit real model configuration available | `.\.venv\Scripts\python.exe -m pytest examples/code_review_agent/tests/integration -q -m real_llm` | explicit real mode succeeds; canonical finding identity/severity/confidence/bucket unchanged; LLM input plaintext-free |

## H. Release regression

| ID | Gate | Command | Required evidence |
|---|---|---|---|
| H-01 | Complete ordinary CI | `.\.venv\Scripts\python.exe -m pytest examples/code_review_agent/tests -q -m "not container and not real_llm"` | exit=0; no required test skipped; pass count recorded |
| H-02 | Static style gate | `.\.venv\Scripts\python.exe -m flake8 examples/code_review_agent` | exit=0; zero violations |

## Acceptance

- Required cases: A–F and H all pass.
- Optional cases: G pass or skip only for their documented prerequisites.
- AC2 is reported as public-proxy evidence, never as proof of hidden samples.
- Progress notes and test artifacts contain no plaintext credential values.

Total: **54 cases**.
