# QA Test Progress — Automatic Code Review Agent

> Total: 46
>
> ✅ Pass: 14 | ❌ Fail: 0 | ⏭️ Skip: 0 | 🔧 Fix: 0 | ⬜ Pending: 32
>
> Evidence must come from the current execution session. Do not record raw secrets, diff content, environment values, or absolute local paths.

<!-- STATUS: ⬜ pending | ✅ pass | ❌ fail | ⏭️ optional prerequisite unavailable | 🔧 fix applied, retest required -->

## A. Specification and readiness

| Status | ID | Title | Note |
|---|---|---|---|
| ✅ | A-01 | Seven-chapter source and references | command=".\.venv\Scripts\python.exe .github/skills/auto-coder/scripts/sync_spec.py --force; .\.venv\Scripts\python.exe .github/skills/qa-tester/scripts/qa_bootstrap.py check-spec", exit=0, chapters=7, references=7, hash_match=true, test_layers_valid=true, duration_ms=2608 |
| ✅ | A-02 | Python and dependency readiness | command=".\.venv\Scripts\python.exe .github/skills/qa-tester/scripts/qa_bootstrap.py status", exit=0, python=3.12.10, supported=true, test_layers_valid=true, top_level_fixtures_exists=false, duration_ms=154 |
| ✅ | A-03 | Layered skeleton and test discovery | command=".\.venv\Scripts\python.exe -m pytest examples/code_review_agent/tests --collect-only -q", exit=0, collected=6, collected_layer=unit, import_errors=0, duration_ms=989 |
| ✅ | A-04 | ReviewConfig and report schema | command=".\.venv\Scripts\python.exe -m pytest examples/code_review_agent/tests/unit/test_config.py -q", exit=0, pytest="6 passed", test_layers=5, top_level_fixtures=0, digest_len=64, schema_required=15, duration_ms=967 |

## B. Deterministic modules

| Status | ID | Title | Note |
|---|---|---|---|
| ✅ | B-01 | ChangeSet and diff parser | command=".\.venv\Scripts\python.exe -m pytest examples/code_review_agent/tests/unit/test_diff_parser.py -q", exit=0, pytest="11 passed", edge_cases=11, input_hash_tests=3 |
| ✅ | B-02 | Input and staging boundary | command=".\\.venv\\Scripts\\python.exe -m pytest examples/code_review_agent/tests/integration/test_inputs.py -q", exit=0, pytest="11 passed", input_forms=4, repo_untracked_added=true, binary_skipped=1, escape_rejections=3, plaintext_log_hits=0, duration_ms=3300 |
| ✅ | B-03 | Detect-then-redact | command=".\\.venv\\Scripts\\python.exe -m pytest examples/code_review_agent/tests/unit/test_redaction.py -q", exit=0, corpus=48, benign=10, plaintext_hits=0 |
| ✅ | B-04 | Security rules and literal scope | command=".\\.venv\\Scripts\\python.exe -m pytest examples/code_review_agent/tests/unit/test_rules.py -q -k \"security or secret\"", exit=0, pytest="6 passed", heuristic_rule_ids=7, qualified_variant_hits=4, literal_false_positives=0 |
| ✅ | B-05 | Async and resource rules | command=".\\.venv\\Scripts\\python.exe -m pytest examples/code_review_agent/tests/unit/test_rules.py -q -k \"async or resource\"", exit=0, pytest="6 passed", async_rule_ids=2, resource_rule_ids=2 |
| ✅ | B-06 | DB lifecycle and missing tests | command=".\\.venv\\Scripts\\python.exe -m pytest examples/code_review_agent/tests/unit/test_rules.py -q -k \"db or missing\"", exit=0, pytest="5 passed", db_rule_ids=2, missing_tests_confidence=0.65 |
| ✅ | B-07 | Changed-line AST | command=".\.venv\Scripts\python.exe -m pytest examples/code_review_agent/tests/unit/test_rules_ast.py -q", exit=0, pytest="10 passed", ast_variant_hits=9, shadowed_false_positives=0, historical_ignored=true, incomplete_parse_calls=0, parse_warning_recorded=true |
| ✅ | B-08 | Stable dedup and buckets | command=".\.venv\Scripts\python.exe -m pytest examples/code_review_agent/tests/unit/test_dedup.py -q", exit=0, pytest="8 passed", dedup_key_fields=3, boundary_values="0.50/0.80/1.00", permutation_stable=true, duration_ms=1147 |
| ✅ | B-09 | Five-table store | command=".\.venv\Scripts\python.exe -m pytest examples/code_review_agent/tests/integration/test_store.py -q", exit=0, pytest="3 passed", tables=5, bundle_domains=5, plaintext_hits=0, duration_ms=3306 |
| ⬜ | B-10 | Canonical reports | |
| ✅ | B-11 | Metrics and Telemetry | command=".\\.venv\\Scripts\\python.exe -m pytest examples/code_review_agent/tests/unit/test_metrics.py -q", exit=0, pytest="4 passed", snapshot_fields=17, telemetry_stages=5, filter_counts="deny=1/review=1", telemetry_allowlist_only=true, plaintext_hits=0 |

## C. Eight public fixtures

| Status | ID | Title | Note |
|---|---|---|---|
| ⬜ | C-01 | 01_clean | |
| ⬜ | C-02 | 02_security | |
| ⬜ | C-03 | 03_async_leak | |
| ⬜ | C-04 | 04_db_lifecycle | |
| ⬜ | C-05 | 05_missing_tests | |
| ⬜ | C-06 | 06_duplicate_finding | |
| ⬜ | C-07 | 07_sandbox_failure | |
| ⬜ | C-08 | 08_secret_redaction | |

## D. Sandbox and governance security

| Status | ID | Title | Note |
|---|---|---|---|
| ✅ | D-01 | Execution manifest integrity | command=".\\.venv\\Scripts\\python.exe -m pytest examples/code_review_agent/tests/integration/test_skill_scripts.py -q -k manifest", exit=0, pytest="1 passed", registered_scripts=2, sha256_matches=2, timeout_seconds=30, max_output_bytes=1048576, duration_ms=1098 |
| ⬜ | D-02 | Filter short-circuit | |
| ⬜ | D-03 | Path and input escape | |
| ⬜ | D-04 | Environment allowlist | |
| ⬜ | D-05 | Timeout as data | |
| ⬜ | D-06 | Output limits | |
| ⬜ | D-07 | Runtime network policy | |
| ⬜ | D-08 | All-sink redaction | |

## E. CLI, persistence, and failure semantics

| Status | ID | Title | Note |
|---|---|---|---|
| ⬜ | E-01 | Idempotent database initialization | |
| ⬜ | E-02 | Zero-Key local dry-run | |
| ⬜ | E-03 | Show/list task bundle | |
| ⬜ | E-04 | Alternate SQL URL | |
| ⬜ | E-05 | Exit codes | |
| ⬜ | E-06 | Partial failure continues | |

## F. Offline evaluation gates

| Status | ID | Title | Note |
|---|---|---|---|
| ⬜ | F-01 | Public corpus and eight fixtures | |
| ⬜ | F-02 | AC2 public proxy | |
| ⬜ | F-03 | AC5 redaction rate | |
| ⬜ | F-04 | AC6 wall-clock budget | |
| ⬜ | F-05 | Summary and optional history | |

## G. Optional integrations

| Status | ID | Title | Note |
|---|---|---|---|
| ⬜ | G-01 | Container integration | |
| ⬜ | G-02 | Real LLM integration | |

## H. Release regression

| Status | ID | Title | Note |
|---|---|---|---|
| ⬜ | H-01 | Complete ordinary CI | |
| ⬜ | H-02 | Static style gate | |
