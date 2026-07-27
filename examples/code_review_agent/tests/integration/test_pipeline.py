#
# Tencent is pleased to support the open source community by making trpc-agent-python available.
#
# Copyright (C) 2026 Tencent. All rights reserved.
#
# trpc-agent-python is licensed under the Apache License Version 2.0.
#

"""Integration tests for the one-path review pipeline."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from codereview.inputs import FixturePayload  # noqa: E402
from codereview.pipeline import ReviewPipeline  # noqa: E402
from codereview.store import SqlReviewStore  # noqa: E402


class _AllowGovernance:
    """提供允许执行且不包含敏感内容的最小治理端口替身。"""

    def decide(self, **_arguments: Any) -> dict[str, object]:
        """返回允许决定和一条可落库的治理事件。"""

        return {
            "action": "allow",
            "events": [
                {
                    "stage": "pre_execution",
                    "target": "run_checks",
                    "action": "allow",
                    "rule": "manifest",
                    "reasons": ["manifest_verified"],
                }
            ],
            "warnings": [],
        }


class _DenyGovernance:
    """提供拒绝决定，验证 pipeline 不会绕过 Filter 执行沙箱。"""

    def decide(self, **_arguments: Any) -> dict[str, object]:
        """返回包含安全原因代码的拒绝治理事件。"""

        return {
            "action": "deny",
            "events": [
                {
                    "stage": "pre_execution",
                    "target": "run_checks",
                    "action": "deny",
                    "rule": "network_policy",
                    "reasons": ["network_proof_missing"],
                }
            ],
            "warnings": [],
        }


class _SecretFindingSandbox:
    """模拟在隔离任务域中检出真实格式凭据的运行时端口。"""

    runtime_type = "fake"

    def __init__(self, secret: str) -> None:
        """保存仅用于模拟沙箱原始 finding 的合成凭据。"""

        self._secret = secret
        self.execute_calls = 0
        self.cleanup_calls = 0

    def execute(self, **_arguments: Any) -> dict[str, object]:
        """返回尚未经过宿主二次脱敏的 sandbox finding。"""

        self.execute_calls += 1
        return {
            "status": "ok",
            "exit_code": 0,
            "timed_out": False,
            "truncated": False,
            "stdout_excerpt": self._secret,
            "stderr_excerpt": "",
            "error_type": None,
            "duration_ms": 7,
            "findings": [
                {
                    "severity": "high",
                    "category": "secrets",
                    "file": "config/.env",
                    "line": 1,
                    "line_side": "new",
                    "title": "轮换已提交的凭据",
                    "evidence": f"TOKEN={self._secret}",
                    "recommendation": "轮换该凭据。",
                    "confidence": 0.99,
                    "source": "rule-engine",
                    "rule_id": "secrets.github-pat",
                }
            ],
        }

    def cleanup(self, **_arguments: Any) -> None:
        """记录 pipeline 在 finally 中释放了任务 workspace。"""

        self.cleanup_calls += 1


class _TimeoutCleanupFailSandbox:
    """模拟超时结果与 workspace 清理失败的隔离运行时端口。"""

    runtime_type = "fake"

    def __init__(self) -> None:
        """初始化可验证的执行和清理调用计数。"""

        self.execute_calls = 0
        self.cleanup_calls = 0

    def execute(self, **_arguments: Any) -> dict[str, object]:
        """返回超时数据，要求 pipeline 转为 warning 而非崩溃。"""

        self.execute_calls += 1
        return {
            "status": "timeout",
            "exit_code": None,
            "timed_out": True,
            "truncated": False,
            "stdout_excerpt": "",
            "stderr_excerpt": "",
            "error_type": "timeout",
            "duration_ms": 30,
            "findings": [],
        }

    def cleanup(self, **_arguments: Any) -> None:
        """模拟清理失败，异常文本不应进入任何持久化出口。"""

        self.cleanup_calls += 1
        raise OSError(r"C:\sensitive-workspace\cleanup-failed")


def _db_url(path: Path) -> str:
    """返回隔离测试数据库的 SQLAlchemy URL。"""

    return f"sqlite+pysqlite:///{path.as_posix()}"


def test_pipeline_redacts_sandbox_output_and_persists_review_bundle(tmp_path: Path) -> None:
    """验证唯一 pipeline 链路输出报告、五类 DB 记录且不泄漏原始凭据。"""

    secret = "ghp_" + "a" * 36
    database = tmp_path / "review.db"
    sandbox = _SecretFindingSandbox(secret)
    store = SqlReviewStore(_db_url(database))
    pipeline = ReviewPipeline(
        store=store,
        governance=_AllowGovernance(),
        sandbox=sandbox,
        output_dir=tmp_path / "reports",
        task_id_factory=lambda: "pipeline-task-001",
    )

    result = pipeline.run(
        fixture=FixturePayload(
            payload_type="files",
            file_contents={"config/.env": f"TOKEN={secret}\n"},
        )
    )
    bundle = store.get_task_bundle(result.task_id)
    serialized_bundle = json.dumps(bundle, ensure_ascii=False, sort_keys=True)

    assert result.status == "completed"
    assert sandbox.execute_calls == 1
    assert sandbox.cleanup_calls == 1
    assert bundle is not None
    assert len(bundle["sandbox_runs"]) == 1
    assert len(bundle["filter_events"]) == 1
    assert len(bundle["findings"]) == 1
    assert bundle["report"]["report"] == result.report
    assert result.report["findings"][0]["category"] == "secrets"
    assert secret not in serialized_bundle
    assert secret.encode("utf-8") not in database.read_bytes()
    assert secret not in result.json_path.read_text(encoding="utf-8")
    assert secret not in result.markdown_path.read_text(encoding="utf-8")


def test_pipeline_converts_timeout_and_cleanup_failure_to_warnings(tmp_path: Path) -> None:
    """验证非致命沙箱失败仍生成报告，并在 finally 中记录无路径清理告警。"""

    sandbox = _TimeoutCleanupFailSandbox()
    store = SqlReviewStore(_db_url(tmp_path / "review.db"))
    pipeline = ReviewPipeline(
        store=store,
        governance=_AllowGovernance(),
        sandbox=sandbox,
        output_dir=tmp_path / "reports",
        task_id_factory=lambda: "pipeline-task-timeout",
    )

    result = pipeline.run(
        fixture=FixturePayload(
            payload_type="files",
            file_contents={"src/service.py": "def run():\n    return None\n"},
        )
    )
    bundle = store.get_task_bundle(result.task_id)
    warning_codes = {warning["code"] for warning in result.report["warnings"]}
    serialized_bundle = json.dumps(bundle, ensure_ascii=False, sort_keys=True)

    assert result.status == "completed_with_warnings"
    assert sandbox.execute_calls == 1
    assert sandbox.cleanup_calls == 1
    assert bundle is not None
    assert bundle["sandbox_runs"][0]["status"] == "timeout"
    assert bundle["sandbox_runs"][0]["timed_out"] is True
    assert {"sandbox_timeout", "workspace_cleanup_error"} <= warning_codes
    assert "C:\\sensitive-workspace" not in serialized_bundle
    assert result.json_path.exists()
    assert result.markdown_path.exists()


def test_pipeline_short_circuits_denied_sandbox_execution(tmp_path: Path) -> None:
    """验证拒绝治理只留审计和 warning，不允许沙箱产生任何副作用。"""

    sandbox = _TimeoutCleanupFailSandbox()
    store = SqlReviewStore(_db_url(tmp_path / "review.db"))
    pipeline = ReviewPipeline(
        store=store,
        governance=_DenyGovernance(),
        sandbox=sandbox,
        output_dir=tmp_path / "reports",
        task_id_factory=lambda: "pipeline-task-denied",
    )

    result = pipeline.run(
        fixture=FixturePayload(
            payload_type="files",
            file_contents={"src/service.py": "def run():\n    return None\n"},
        )
    )
    bundle = store.get_task_bundle(result.task_id)

    assert result.status == "completed_with_warnings"
    assert sandbox.execute_calls == 0
    assert sandbox.cleanup_calls == 1
    assert bundle is not None
    assert bundle["sandbox_runs"] == []
    assert bundle["filter_events"][0]["action"] == "deny"
    assert "filter_deny" in {warning["code"] for warning in result.report["warnings"]}
