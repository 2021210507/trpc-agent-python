#
# Tencent is pleased to support the open source community by making trpc-agent-python available.
#
# Copyright (C) 2026 Tencent. All rights reserved.
#
# trpc-agent-python is licensed under the Apache License Version 2.0.
#

"""Offline evaluation entry-point contracts for D4."""

from __future__ import annotations

import json
import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest


PROJECT_ROOT = Path(__file__).resolve().parents[2]
EVALUATE_PATH = PROJECT_ROOT / "evaluate.py"
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import evaluate  # noqa: E402


@pytest.fixture(scope="module")
def evaluation_summary(tmp_path_factory: pytest.TempPathFactory) -> dict[str, object]:
    """执行一次真实 local Skill 评测，并返回其不含原始语料的摘要。"""

    output_dir = tmp_path_factory.mktemp("evaluation")
    completed = subprocess.run(
        [
            sys.executable,
            str(EVALUATE_PATH),
            "--sandbox",
            "local",
            "--output-dir",
            str(output_dir),
        ],
        cwd=output_dir,
        check=False,
        capture_output=True,
        encoding="utf-8",
        text=True,
        timeout=120,
    )
    assert completed.returncode == 0, completed.stderr
    summary_path = output_dir / "eval_summary.json"
    assert summary_path.is_file()
    assert not (output_dir / "review.db").exists()
    return json.loads(summary_path.read_text(encoding="utf-8"))


def test_evaluate_metrics_meet_public_proxy_gates(evaluation_summary: dict[str, object]) -> None:
    """验证公开代理语料的 fixture、召回、误报占比和 P/R/F1 统计。"""

    assert evaluation_summary["fixture_summary"] == {"passed": 8, "total": 8}
    assert evaluation_summary["corpus"]["boundary_cases"] >= 8
    metrics = evaluation_summary["metrics"]
    assert isinstance(metrics, dict)
    assert metrics["high_risk_recall"] >= 0.80
    assert metrics["finding_false_positive_share"] <= 0.15
    assert metrics["benign_secret_false_positives"] == 0
    assert set(("precision", "recall", "f1")) <= set(metrics)


def test_evaluate_redact_and_duration_gates(evaluation_summary: dict[str, object]) -> None:
    """验证密钥检测率、所有评测出口脱敏结果与统一墙钟预算。"""

    metrics = evaluation_summary["metrics"]
    assert isinstance(metrics, dict)
    assert metrics["redaction_detection_rate"] >= 0.95
    assert metrics["plaintext_hits"] == 0
    assert evaluation_summary["duration_ms"] <= 120_000


def test_evaluate_summary_and_optional_history(tmp_path: Path) -> None:
    """验证摘要包含环境摘要、默认无业务库写入且可显式写入独立历史库。"""

    output_dir = tmp_path / "evaluation"
    history_db = tmp_path / "evaluation_history.db"
    completed = subprocess.run(
        [
            sys.executable,
            str(EVALUATE_PATH),
            "--sandbox",
            "local",
            "--output-dir",
            str(output_dir),
            "--write-db",
            str(history_db),
        ],
        cwd=tmp_path,
        check=False,
        capture_output=True,
        encoding="utf-8",
        text=True,
        timeout=120,
    )
    assert completed.returncode == 0, completed.stderr
    summary = json.loads((output_dir / "eval_summary.json").read_text(encoding="utf-8"))
    assert history_db.is_file()
    assert summary["history"]["enabled"] is True
    assert {"python", "platform", "runtime", "schema_version", "rule_pack_version", "config_digest"} <= set(summary)


def test_evaluate_rejects_real_or_llm_denoise_options(tmp_path: Path) -> None:
    """验证门禁入口固定 fake 模型，拒绝 real 与本期不存在的 LLM 降噪参数。"""

    for forbidden_arguments in (("--model-mode", "real"), ("--llm-denoise",)):
        completed = subprocess.run(
            [sys.executable, str(EVALUATE_PATH), *forbidden_arguments],
            cwd=tmp_path,
            check=False,
            capture_output=True,
            encoding="utf-8",
            text=True,
            timeout=30,
        )
        assert completed.returncode != 0


def test_evaluate_subprocess_environment_is_allowlisted(monkeypatch: pytest.MonkeyPatch) -> None:
    """验证评测子进程环境不携带任意名称或值的宿主敏感变量。"""

    canary_name = "AWS_SECRET_ACCESS_KEY"
    canary_value = "synthetic-canary-value"
    monkeypatch.setenv(canary_name, canary_value)

    environment = evaluate._sanitized_environment()

    assert canary_name not in environment
    assert canary_value not in environment.values()
    assert environment["PYTHONUTF8"] == "1"


def test_evaluate_history_rejects_business_review_schema(tmp_path: Path) -> None:
    """验证评测历史库拒绝业务 review.db 名称和已有业务五表，避免污染审查数据。"""

    business_database = tmp_path / "business.db"
    connection = sqlite3.connect(business_database)
    try:
        connection.execute("CREATE TABLE cr_review_task (id TEXT PRIMARY KEY)")
        connection.commit()
    finally:
        connection.close()

    with pytest.raises(ValueError, match="evaluation_history_database_invalid"):
        evaluate._write_history(business_database, {"status": "safe"})
    with pytest.raises(ValueError, match="evaluation_history_database_invalid"):
        evaluate._write_history(tmp_path / "review.db", {"status": "safe"})


def test_evaluate_returns_nonzero_when_a_hard_gate_fails(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """验证任一公开代理硬门禁失败时入口返回非零，而不是仅在摘要中记录失败。"""

    monkeypatch.setattr(evaluate, "_run_fixture_suite", lambda *_arguments: (8, 0))
    monkeypatch.setattr(
        evaluate,
        "_evaluate_corpus",
        lambda *_arguments: {
            "corpus": {"positive_cases": 20, "clean_negative_cases": 10, "secret_cases": 48},
            "metrics": {
                "high_risk_recall": 0.79,
                "finding_false_positive_share": 0.0,
                "redaction_detection_rate": 1.0,
                "plaintext_hits": 0,
                "benign_secret_false_positives": 0,
            },
        },
    )
    monkeypatch.setattr(evaluate, "_observe_blind_spots", lambda *_arguments: (4, 0))

    exit_code = evaluate.main(["--sandbox", "local", "--output-dir", str(tmp_path / "evaluation")])

    assert exit_code == 1
