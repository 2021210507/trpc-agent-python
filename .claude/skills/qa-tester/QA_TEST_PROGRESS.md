# QA Test Progress — Automatic Code Review Agent

> Total: 46
>
> ✅ Pass: 41 | ❌ Fail: 0 | ⏭️ Skip: 0 | 🔧 Fix: 0 | ⬜ Pending: 5
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
| ✅ | B-10 | Canonical reports | command=".\.venv\Scripts\python.exe -m pytest examples/code_review_agent/tests/integration/test_report.py -q", exit=0, pytest="5 passed", report_sections=8, stable_bytes=true, db_report_matches_json=true, plaintext_hits=0, atomic_partial_targets=0 |
| ✅ | B-11 | Metrics and Telemetry | command=".\\.venv\\Scripts\\python.exe -m pytest examples/code_review_agent/tests/unit/test_metrics.py -q", exit=0, pytest="4 passed", snapshot_fields=17, telemetry_stages=5, filter_counts="deny=1/review=1", telemetry_allowlist_only=true, plaintext_hits=0 |

## C. Eight public fixtures

| Status | ID | Title | Note |
|---|---|---|---|
| ✅ | C-01 | 01_clean | command=".\.venv\Scripts\python.exe -m pytest examples/code_review_agent/tests/e2e/test_fixtures_e2e.py -q -k \"real_local_skill and 01_clean\" --basetemp <sanitized-temp> -p no:cacheprovider", exit=0, pytest="1 passed", entry=cli_local, findings=0, bundle_domains=5 |
| ✅ | C-02 | 02_security | command=".\.venv\Scripts\python.exe -m pytest examples/code_review_agent/tests/e2e/test_fixtures_e2e.py -q -k \"real_local_skill and 02_security\" --basetemp <sanitized-temp> -p no:cacheprovider", exit=0, pytest="1 passed", entry=cli_local, security_findings_ge=2, severity="high_or_critical" |
| ✅ | C-03 | 03_async_leak | command=".\.venv\Scripts\python.exe -m pytest examples/code_review_agent/tests/e2e/test_fixtures_e2e.py -q -k \"real_local_skill and 03_async_leak\" --basetemp <sanitized-temp> -p no:cacheprovider", exit=0, pytest="1 passed", entry=cli_local, categories="async-errors/resource-leak", resource_bucket=needs_human_review |
| ✅ | C-04 | 04_db_lifecycle | command=".\.venv\Scripts\python.exe -m pytest examples/code_review_agent/tests/e2e/test_fixtures_e2e.py -q -k \"real_local_skill and 04_db_lifecycle\" --basetemp <sanitized-temp> -p no:cacheprovider", exit=0, pytest="1 passed", entry=cli_local, db_lifecycle_ge=2, bundle_domains=5 |
| ✅ | C-05 | 05_missing_tests | command=".\.venv\Scripts\python.exe -m pytest examples/code_review_agent/tests/e2e/test_fixtures_e2e.py -q -k \"real_local_skill and 05_missing_tests\" --basetemp <sanitized-temp> -p no:cacheprovider", exit=0, pytest="1 passed", entry=cli_local, findings=0, human_review_category=missing_tests |
| ✅ | C-06 | 06_duplicate_finding | command=".\.venv\Scripts\python.exe -m pytest examples/code_review_agent/tests/e2e/test_fixtures_e2e.py -q -k \"real_local_skill and 06_duplicate_finding\" --basetemp <sanitized-temp> -p no:cacheprovider", exit=0, pytest="1 passed", entry=cli_local, security_results=1, also_matched_nonempty=true |
| ✅ | C-07 | 07_sandbox_failure | command=".\.venv\Scripts\python.exe -m pytest examples/code_review_agent/tests/e2e/test_fixtures_e2e.py -q -k \"public_fixtures_generate and 07_sandbox_failure\" --basetemp <sanitized-temp> -p no:cacheprovider", exit=0, pytest="1 passed", entry=fake_runtime_injection, status=completed_with_warnings, sandbox_runs=1 |
| ✅ | C-08 | 08_secret_redaction | command=".\.venv\Scripts\python.exe -m pytest examples/code_review_agent/tests/e2e/test_fixtures_e2e.py -q -k \"real_local_skill and 08_secret_redaction\" --basetemp <sanitized-temp> -p no:cacheprovider", exit=0, pytest="1 passed", entry=cli_local, secret_findings_ge=3, plaintext_hits=0 |

## D. Sandbox and governance security

| Status | ID | Title | Note |
|---|---|---|---|
| ✅ | D-01 | Execution manifest integrity | command=".\\.venv\\Scripts\\python.exe -m pytest examples/code_review_agent/tests/integration/test_skill_scripts.py -q -k manifest", exit=0, pytest="1 passed", registered_scripts=2, sha256_matches=2, timeout_seconds=30, max_output_bytes=1048576, duration_ms=1098 |
| ✅ | D-02 | Filter short-circuit | command=".\.venv\Scripts\python.exe -m pytest examples/code_review_agent/tests/integration/test_governance.py -q -k \"deny or human or sentinel\"", exit=0, pytest="3 passed", blocked_requests=5, sandbox_runs=0, plaintext_hits=0 |
| ⬜ | D-03 | Path and input escape | |
| ⬜ | D-04 | Environment allowlist | |
| ✅ | D-05 | Timeout as data | command=".\.venv\Scripts\python.exe -m pytest examples/code_review_agent/tests/integration/test_sandbox_safety.py -q -k timeout", exit=0, pytest="2 passed", timed_out=true, structured_error=timeout, duration_s=5.5 |
| ✅ | D-06 | Output limits | command=".\.venv\Scripts\python.exe -m pytest examples/code_review_agent/tests/integration/test_sandbox_safety.py -q -k \"output or trunc\"", exit=0, pytest="2 passed", output_limit_bytes=1048576, truncated_status=error, duration_s=5.4 |
| ✅ | D-07 | Runtime network policy | command=".\.venv\Scripts\python.exe -m pytest examples/code_review_agent/tests/integration/test_governance.py -q -k \"network or cube or local or container\"", exit=0, pytest="2 passed", container_mode=none, cube_action=deny, local_warning=1 |
| ✅ | D-08 | All-sink redaction | command=".\.venv\Scripts\python.exe -m pytest examples/code_review_agent/tests/integration/test_pipeline.py -q -k \"secret or redact or plaintext\"", exit=0, pytest="1 passed", secret_finding=1, plaintext_hits=0, duration_s=5.5 |

## E. CLI, persistence, and failure semantics

| Status | ID | Title | Note |
|---|---|---|---|
| ✅ | E-01 | Idempotent database initialization | command=".\.venv\Scripts\python.exe -m pytest examples/code_review_agent/tests/e2e/test_cli.py -q -k init_db", exit=0, pytest="1 passed", init_exit=0, tables=5, duration_s=18.1 |
| ✅ | E-02 | Zero-Key local dry-run | command=".\.venv\Scripts\python.exe -m pytest examples/code_review_agent/tests/e2e/test_cli.py -q -k dry_run --basetemp <sanitized-temp> -p no:cacheprovider", exit=0, pytest="1 passed", model_key_required=false, model_path=fake, sandbox=local, reports=2, duration_s=23.1 |
| ✅ | E-03 | Show/list task bundle | command=".\.venv\Scripts\python.exe -m pytest examples/code_review_agent/tests/e2e/test_cli.py -q -k \"show or list\"", exit=0, pytest="1 passed", bundle_domains=5, sandbox_runs=1, filter_events=1, duration_s=17.0 |
| ✅ | E-04 | Alternate SQL URL | command=".\.venv\Scripts\python.exe -m pytest examples/code_review_agent/tests/e2e/test_cli.py -q -k db_url", exit=0, pytest="1 passed", temporary_sqlite=true, business_review_db_created=false, duration_s=16.3 |
| ✅ | E-05 | Exit codes | command=".\.venv\Scripts\python.exe -m pytest examples/code_review_agent/tests/e2e/test_cli.py -q -k \"exit or fail_on_severity\" --basetemp <sanitized-temp> -p no:cacheprovider", exit=0, pytest="2 passed", exit_codes="0/1/2", invalid_request=2, container_available_exit=0 |
| ✅ | E-06 | Partial failure continues | command=".\.venv\Scripts\python.exe -m pytest examples/code_review_agent/tests/integration/test_pipeline.py -q -k \"failure or warning or cleanup\"", exit=0, pytest="1 passed", status=completed_with_warnings, sandbox_runs=1, cleanup_warning=true |

## F. Offline evaluation gates

| Status | ID | Title | Note |
|---|---|---|---|
| ✅ | F-01 | Public corpus and eight fixtures | command=".\.venv\Scripts\python.exe examples/code_review_agent/evaluate.py --sandbox local --output-dir <sanitized-temp>", exit=0, fixtures="8/8", boundary_cases=8, eval_summary=true, duration_s=58.4 |
| ✅ | F-02 | AC2 public proxy | command=".\.venv\Scripts\python.exe -m pytest examples/code_review_agent/tests/e2e/test_evaluate.py -q -k metrics --basetemp <sanitized-temp> -p no:cacheprovider", exit=0, pytest="1 passed", high_risk_recall=1.0, fp_share=0.0, p_r_f1=true, benign_fp=0, duration_s=59.6 |
| ✅ | F-03 | AC5 redaction rate | command=".\.venv\Scripts\python.exe -m pytest examples/code_review_agent/tests/e2e/test_evaluate.py -q -k redact --basetemp <sanitized-temp> -p no:cacheprovider", exit=0, pytest="1 passed", redaction_detection_rate=1.0, plaintext_hits=0, duration_s=58.7 |
| ✅ | F-04 | AC6 wall-clock budget | command=".\.venv\Scripts\python.exe -m pytest examples/code_review_agent/tests/e2e/test_evaluate.py -q -k duration --basetemp <sanitized-temp> -p no:cacheprovider", exit=0, pytest="1 passed", duration_ms_lt=120000, model_mode=fake, runtime=local, duration_s=57.7 |
| ✅ | F-05 | Summary and optional history | command=".\.venv\Scripts\python.exe -m pytest examples/code_review_agent/tests/e2e/test_evaluate.py -q -k \"summary or write_db or history_rejects\" --basetemp <sanitized-temp> -p no:cacheprovider", exit=0, pytest="2 passed", history_opt_in=true, business_schema_rejected=true, summary_digests=3, duration_s=59.5 |

## G. Optional integrations

| Status | ID | Title | Note |
|---|---|---|---|
| ✅ | G-01 | Container integration | command=".\.venv\Scripts\python.exe -m pytest examples/code_review_agent/tests/integration/test_sandbox_safety.py -q -m container --basetemp <sanitized-temp> -p no:cacheprovider", exit=0, pytest="2 passed", network_mode=none, sandbox_runs=2, plaintext_hits=0 |
| ⬜ | G-02 | Real LLM integration | |

## H. Release regression

| Status | ID | Title | Note |
|---|---|---|---|
| ⬜ | H-01 | Complete ordinary CI | |
| ⬜ | H-02 | Static style gate | |
