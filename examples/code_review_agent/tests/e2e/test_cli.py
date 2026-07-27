#
# Tencent is pleased to support the open source community by making trpc-agent-python available.
#
# Copyright (C) 2026 Tencent. All rights reserved.
#
# trpc-agent-python is licensed under the Apache License Version 2.0.
#

"""End-to-end tests for the public code-review command line interface."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
CLI_PATH = PROJECT_ROOT / "run_agent.py"


def _db_url(path: Path) -> str:
    """构造仅供本测试进程使用的临时 SQLite URL。"""

    return f"sqlite+pysqlite:///{path.as_posix()}"


def _run_cli(tmp_path: Path, *arguments: str) -> subprocess.CompletedProcess[str]:
    """在仓库虚拟环境解释器下执行 CLI，并移除可能影响离线路径的模型凭据。"""

    environment = os.environ.copy()
    for name in tuple(environment):
        if "API_KEY" in name or "TOKEN" in name or "PASSWORD" in name:
            environment.pop(name)
    environment["PYTHONUTF8"] = "1"
    return subprocess.run(
        [sys.executable, str(CLI_PATH), *arguments],
        cwd=tmp_path,
        env=environment,
        check=False,
        capture_output=True,
        encoding="utf-8",
        text=True,
        timeout=120,
    )


def _write_high_severity_file(tmp_path: Path) -> Path:
    """写入能够触发确定性 shell 注入规则的最小快照文件。"""

    source = tmp_path / "src" / "service.py"
    source.parent.mkdir()
    source.write_text(
        "import subprocess\n\nsubprocess.run('echo hello', shell=True)\n",
        encoding="utf-8",
    )
    return source


def _review_arguments(database: Path, source: Path, output_dir: Path) -> list[str]:
    """返回每个 CLI 评审场景共享的显式 local dry-run 参数。"""

    return [
        "review",
        "--files",
        str(source.relative_to(source.parents[1])),
        "--input-root",
        str(source.parents[1]),
        "--db-url",
        _db_url(database),
        "--output-dir",
        str(output_dir),
        "--sandbox",
        "local",
        "--dry-run",
    ]


def test_dry_run_db_url_review_show_list_and_init_db_use_one_sqlite_bundle(tmp_path: Path) -> None:
    """验证 review→show→list→init-db 共享临时数据库且不需要模型 Key 或 Docker。"""

    source = _write_high_severity_file(tmp_path)
    database = tmp_path / "review.db"
    output_dir = tmp_path / "reports"

    initialized = _run_cli(tmp_path, "init-db", "--db-url", _db_url(database))
    reviewed = _run_cli(tmp_path, *_review_arguments(database, source, output_dir))

    assert initialized.returncode == 0, initialized.stderr
    assert reviewed.returncode == 0, reviewed.stderr
    payload = json.loads(reviewed.stdout)
    assert payload["status"] in {"completed", "completed_with_warnings"}
    assert payload["task_id"].startswith("review-")
    assert (output_dir / "review_report.json").is_file()
    assert (output_dir / "review_report.md").is_file()

    shown = _run_cli(tmp_path, "show", payload["task_id"], "--db-url", _db_url(database))
    listed = _run_cli(tmp_path, "list", "--db-url", _db_url(database))

    assert shown.returncode == 0, shown.stderr
    shown_bundle = json.loads(shown.stdout)
    assert shown_bundle["task"]["id"] == payload["task_id"]
    assert len(shown_bundle["sandbox_runs"]) == 1
    assert len(shown_bundle["filter_events"]) == 1
    assert shown_bundle["report"] is not None
    assert listed.returncode == 0, listed.stderr
    assert payload["task_id"] in {task["id"] for task in json.loads(listed.stdout)["tasks"]}
    assert not (tmp_path / "out" / "review.db").exists()


def test_fail_on_severity_returns_one_only_at_requested_boundary(tmp_path: Path) -> None:
    """验证高危 finding 在阈值命中时返回 1，而关闭阈值时保持成功退出。"""

    source = _write_high_severity_file(tmp_path)
    database = tmp_path / "review.db"
    base_arguments = _review_arguments(database, source, tmp_path / "reports")

    normal = _run_cli(tmp_path, *base_arguments)
    failing = _run_cli(tmp_path, *base_arguments, "--fail-on-severity", "high")

    assert normal.returncode == 0, normal.stderr
    assert failing.returncode == 1, failing.stderr


def test_invalid_and_strict_container_requests_exit_two(tmp_path: Path) -> None:
    """验证未知参数、互斥输入和未就绪的严格 container 均使用配置错误退出码。"""

    source = _write_high_severity_file(tmp_path)
    database = tmp_path / "review.db"
    invalid = _run_cli(
        tmp_path,
        "review",
        "--files",
        str(source),
        "--repo-path",
        str(tmp_path),
        "--db-url",
        _db_url(database),
    )
    forbidden = _run_cli(tmp_path, "review", "--command", "whoami")
    strict_container = _run_cli(
        tmp_path,
        "review",
        "--files",
        str(source.relative_to(tmp_path)),
        "--input-root",
        str(tmp_path),
        "--db-url",
        _db_url(database),
        "--sandbox",
        "container",
    )

    assert invalid.returncode == 2
    assert forbidden.returncode == 2
    assert strict_container.returncode == 2
