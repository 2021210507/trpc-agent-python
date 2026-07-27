#
# Tencent is pleased to support the open source community by making trpc-agent-python available.
#
# Copyright (C) 2026 Tencent. All rights reserved.
#
# trpc-agent-python is licensed under the Apache License Version 2.0.
#

"""Public-fixture end-to-end contracts for the deterministic review pipeline."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_ROOT = PROJECT_ROOT / "skills" / "code-review" / "scripts"
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
if str(SCRIPTS_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_ROOT))

from codereview.inputs import FixturePayload  # noqa: E402
from codereview.pipeline import ReviewPipeline  # noqa: E402
from codereview.redaction import contains_plaintext_secret  # noqa: E402
from codereview.store import SqlReviewStore  # noqa: E402
from run_checks import _findings  # noqa: E402


FIXTURE_DIR = PROJECT_ROOT / "tests" / "fixtures" / "diffs"
FIXTURE_NAMES = (
    "01_clean",
    "02_security",
    "03_async_leak",
    "04_db_lifecycle",
    "05_missing_tests",
    "06_duplicate_finding",
    "07_sandbox_failure",
    "08_secret_redaction",
)
_CLI_FIXTURE_NAMES = tuple(name for name in FIXTURE_NAMES if name != "07_sandbox_failure")
_SYNTHETIC_SECRETS = (
    "AKIA" + "1234567890ABCDEF",
    "ghp_" + "abcdefghijklmnopqrstuvwxyz0123456789",
    "LongSyntheticPasswordValue123!",
)


class _AllowFixtureGovernance:
    """为公开 fixture 提供固定 allow 审计事件，确保测试仍经过 pipeline 的治理阶段。"""

    def decide(self, **_arguments: Any) -> dict[str, object]:
        """返回不含原始代码或凭据的受控 allow 决策。"""

        return {
            "action": "allow",
            "events": [
                {
                    "stage": "pre_execution",
                    "target": "run_checks",
                    "action": "allow",
                    "rule": "fixture_runtime",
                    "reasons": ["fixture_rule_pack"],
                }
            ],
            "warnings": [],
        }


class _FixtureRuleSandbox:
    """在 fake runtime 中调用同一份 Skill run_checks 规则，避免 fixture 套件依赖 Docker。"""

    runtime_type = "fake"

    def __init__(self, *, expose_secret_in_stdout: bool = False) -> None:
        """记录是否向 sandbox 摘要注入合成密钥，以验证宿主二次脱敏出口。"""

        self._expose_secret_in_stdout = expose_secret_in_stdout

    def execute(self, **arguments: Any) -> dict[str, object]:
        """使用 Skill 的真实确定性规则返回候选 finding，不复制规则实现。"""

        change_set = arguments["change_set"]
        return {
            "status": "ok",
            "exit_code": 0,
            "timed_out": False,
            "truncated": False,
            "stdout_excerpt": _SYNTHETIC_SECRETS[1] if self._expose_secret_in_stdout else "",
            "stderr_excerpt": "",
            "error_type": None,
            "duration_ms": 1,
            "findings": list(_findings(change_set)),
        }

    def cleanup(self, **_arguments: Any) -> None:
        """fake runtime 没有创建 workspace，因此 cleanup 保持无副作用。"""


class _FailedFixtureSandbox:
    """模拟受控 sandbox 非零失败，用于验证报告和数据库仍可交付。"""

    runtime_type = "fake"

    def execute(self, **_arguments: Any) -> dict[str, object]:
        """返回不携带原始命令或路径的非零运行摘要。"""

        return {
            "status": "failed",
            "exit_code": 9,
            "timed_out": False,
            "truncated": False,
            "stdout_excerpt": "",
            "stderr_excerpt": "synthetic_checker_failure",
            "error_type": "nonzero_exit",
            "duration_ms": 1,
            "findings": [],
        }

    def cleanup(self, **_arguments: Any) -> None:
        """fake failure runtime 不保留资源，保证 finally 路径可稳定验证。"""


def _db_url(path: Path) -> str:
    """构造每条 fixture 独占的临时 SQLite URL，避免写入业务数据库。"""

    return f"sqlite+pysqlite:///{path.as_posix()}"


def _fixture_payload(name: str) -> FixturePayload:
    """读取公开 unified diff 数据，保持 fixture 的 diff 载荷语义不变。"""

    return FixturePayload(
        payload_type="diff",
        diff_text=(FIXTURE_DIR / f"{name}.diff").read_text(encoding="utf-8"),
    )


def _run_fixture(name: str, tmp_path: Path) -> tuple[dict[str, Any], SqlReviewStore, Path]:
    """经唯一 ReviewPipeline 执行一条 fixture，并返回 canonical 报告、存储和输出目录。"""

    output_dir = tmp_path / "reports"
    store = SqlReviewStore(_db_url(tmp_path / "review.db"))
    sandbox: Any
    if name == "07_sandbox_failure":
        sandbox = _FailedFixtureSandbox()
    else:
        sandbox = _FixtureRuleSandbox(expose_secret_in_stdout=name == "08_secret_redaction")
    pipeline = ReviewPipeline(
        store=store,
        governance=_AllowFixtureGovernance(),
        sandbox=sandbox,
        output_dir=output_dir,
        task_id_factory=lambda: f"fixture-{name}",
    )
    result = pipeline.run(fixture=_fixture_payload(name))
    return result.report, store, output_dir


def _run_cli_fixture(name: str, tmp_path: Path) -> tuple[dict[str, Any], SqlReviewStore, Path]:
    """通过公开 CLI 运行真实 local Skill，并返回 canonical 报告、临时 SQLite store 和输出目录。"""

    output_dir = tmp_path / "reports"
    database = tmp_path / "review.db"
    environment = os.environ.copy()
    for variable in tuple(environment):
        if "API_KEY" in variable or "TOKEN" in variable or "PASSWORD" in variable:
            environment.pop(variable)
    completed = subprocess.run(
        [
            sys.executable,
            str(PROJECT_ROOT / "run_agent.py"),
            "review",
            "--fixture",
            name,
            "--sandbox",
            "local",
            "--dry-run",
            "--db-url",
            _db_url(database),
            "--output-dir",
            str(output_dir),
        ],
        cwd=tmp_path,
        env=environment,
        check=False,
        capture_output=True,
        encoding="utf-8",
        text=True,
        timeout=120,
    )
    assert completed.returncode == 0, completed.stderr
    result = json.loads(completed.stdout)
    report = json.loads((output_dir / "review_report.json").read_text(encoding="utf-8"))
    assert result["task_id"] == report["task_id"]
    store = SqlReviewStore(_db_url(database))
    store.initialize()
    return report, store, output_dir


def _assert_common_fixture_outputs(
    report: dict[str, Any],
    store: SqlReviewStore,
    output_dir: Path,
) -> dict[str, Any]:
    """断言每条 fixture 都生成同源 JSON、Markdown 与五域可查询数据库 bundle。"""

    json_path = output_dir / "review_report.json"
    markdown_path = output_dir / "review_report.md"
    bundle = store.get_task_bundle(report["task_id"])
    assert json_path.is_file()
    assert markdown_path.is_file()
    assert json.loads(json_path.read_text(encoding="utf-8")) == report
    assert report["task_id"] in markdown_path.read_text(encoding="utf-8")
    assert bundle is not None
    assert bundle["task"]["id"] == report["task_id"]
    assert len(bundle["sandbox_runs"]) == 1
    assert len(bundle["filter_events"]) == 1
    assert bundle["report"] is not None
    return bundle


@pytest.mark.parametrize("fixture_name", FIXTURE_NAMES, ids=FIXTURE_NAMES)
def test_public_fixtures_generate_expected_reports_and_bundles(
    fixture_name: str,
    tmp_path: Path,
) -> None:
    """验证八条公开 fixture 的类别、桶、失败语义与 JSON/Markdown/SQLite 交付契约。"""

    report, store, output_dir = _run_fixture(fixture_name, tmp_path)
    try:
        bundle = _assert_common_fixture_outputs(report, store, output_dir)
        categories = {finding["category"] for finding in report["findings"]}
        reviewed_categories = categories | {
            finding["category"] for finding in report["needs_human_review"]
        }

        if fixture_name == "01_clean":
            assert report["findings"] == []
            assert report["needs_human_review"] == []
        elif fixture_name == "02_security":
            security = [finding for finding in report["findings"] if finding["category"] == "security"]
            assert len(security) >= 2
            assert {finding["severity"] for finding in security} <= {"high", "critical"}
        elif fixture_name == "03_async_leak":
            assert {"async-errors", "resource-leak"} <= reviewed_categories
            assert "resource-leak" in {
                finding["category"] for finding in report["needs_human_review"]
            }
        elif fixture_name == "04_db_lifecycle":
            lifecycle_findings = [
                finding
                for finding in [*report["findings"], *report["needs_human_review"]]
                if finding["category"] == "db-lifecycle"
            ]
            assert "db-lifecycle" in reviewed_categories
            assert len(lifecycle_findings) >= 2
        elif fixture_name == "05_missing_tests":
            assert report["findings"] == []
            assert {finding["category"] for finding in report["needs_human_review"]} == {"missing-tests"}
        elif fixture_name == "06_duplicate_finding":
            security = [finding for finding in report["findings"] if finding["category"] == "security"]
            assert len(security) == 1
            assert security[0]["extra"]["also_matched"]
        elif fixture_name == "07_sandbox_failure":
            assert report["status"] == "completed_with_warnings"
            assert report["findings"] == []
            assert bundle["sandbox_runs"][0]["status"] == "failed"
            assert "sandbox_failed" in {warning["code"] for warning in report["warnings"]}
        elif fixture_name == "08_secret_redaction":
            secret_findings = [finding for finding in report["findings"] if finding["category"] == "secrets"]
            serialized_outputs = "\n".join(
                (
                    json.dumps(report, ensure_ascii=False, sort_keys=True),
                    json.dumps(bundle, ensure_ascii=False, sort_keys=True),
                    (output_dir / "review_report.json").read_text(encoding="utf-8"),
                    (output_dir / "review_report.md").read_text(encoding="utf-8"),
                )
            )
            database_text = (tmp_path / "review.db").read_bytes().decode(
                "utf-8",
                errors="ignore",
            )
            assert len(secret_findings) >= 3
            assert all(finding["line"] not in {4, 5} for finding in secret_findings)
            assert not contains_plaintext_secret(serialized_outputs)
            assert all(secret not in serialized_outputs for secret in _SYNTHETIC_SECRETS)
            assert all(secret not in database_text for secret in _SYNTHETIC_SECRETS)
    finally:
        store.close()


@pytest.mark.parametrize("fixture_name", _CLI_FIXTURE_NAMES, ids=_CLI_FIXTURE_NAMES)
def test_public_fixtures_run_through_cli_with_real_local_skill(
    fixture_name: str,
    tmp_path: Path,
) -> None:
    """验证七条正常公开 fixture 从 CLI 到真实 Skill、JSON、Markdown 和 SQLite bundle 的完整闭环。"""

    report, store, output_dir = _run_cli_fixture(fixture_name, tmp_path)
    try:
        bundle = _assert_common_fixture_outputs(report, store, output_dir)
        all_categories = {
            finding["category"]
            for finding in [*report["findings"], *report["needs_human_review"]]
        }

        assert report["status"] in {"completed", "completed_with_warnings"}
        if fixture_name == "01_clean":
            assert not report["findings"]
        elif fixture_name == "02_security":
            assert sum(finding["category"] == "security" for finding in report["findings"]) >= 2
        elif fixture_name == "03_async_leak":
            assert {"async-errors", "resource-leak"} <= all_categories
        elif fixture_name == "04_db_lifecycle":
            assert "db-lifecycle" in all_categories
        elif fixture_name == "05_missing_tests":
            assert "missing-tests" in all_categories
        elif fixture_name == "06_duplicate_finding":
            security = [finding for finding in report["findings"] if finding["category"] == "security"]
            assert len(security) == 1
        elif fixture_name == "08_secret_redaction":
            assert "secrets" in all_categories
            assert not contains_plaintext_secret(json.dumps(bundle, ensure_ascii=False, sort_keys=True))
    finally:
        store.close()
