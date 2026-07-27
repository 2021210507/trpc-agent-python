#
# Tencent is pleased to support the open source community by making trpc-agent-python available.
#
# Copyright (C) 2026 Tencent. All rights reserved.
#
# trpc-agent-python is licensed under the Apache License Version 2.0.
#

"""Command-line entry point for the automatic code-review Agent."""

from __future__ import annotations

import argparse
import json
import logging
import shutil
import subprocess
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from codereview.config import ReviewConfig
from codereview.governance import (
    ExecutionBudget,
    GovernanceRequest,
    SandboxGovernanceFilter,
)
from codereview.inputs import FixturePayload
from codereview.model_environment import load_model_environment
from codereview.pipeline import PipelineFatalError, ReviewPipeline
from codereview.sandbox import (
    SandboxConfigurationError,
    SdkSkillSandbox,
    build_sandbox_environment,
    create_sandbox_runtime,
)
from codereview.store import DEFAULT_DB_URL, SqlReviewStore, init_db


_PROJECT_ROOT = Path(__file__).resolve().parent
_SKILL_ROOT = _PROJECT_ROOT / "skills" / "code-review"
_MANIFEST_PATH = _SKILL_ROOT / "scripts" / "manifest.json"
_SEVERITY_RANK = {"low": 1, "medium": 2, "high": 3, "critical": 4}


class CliError(ValueError):
    """表示应以退出码 2 返回且不泄露原始异常文本的用户输入或运行配置错误。"""


class PipelineGovernance:
    """把 C1 的受控 Filter 请求适配为 ReviewPipeline 所需的治理端口。"""

    def __init__(self, *, selection: Any, config: ReviewConfig, workspace_root: Path) -> None:
        """绑定已选 runtime、固定配置和仅用于相对路径校验的任务 workspace 根目录。"""

        self._selection = selection
        self._config = config
        self._workspace_root = workspace_root
        self._filter = SandboxGovernanceFilter(_MANIFEST_PATH, config=config)

    def decide(self, **_arguments: Any) -> Mapping[str, Any]:
        """为固定 run_checks 脚本创建无 shell、无敏感环境变量的唯一治理请求。"""

        request = GovernanceRequest(
            script_id="run_checks",
            structured_args={},
            skill_root=_SKILL_ROOT,
            workspace_root=self._workspace_root,
            input_paths=(Path("work/inputs/diff.json"),),
            output_paths=(Path("out/findings.json"),),
            environment=build_sandbox_environment(),
            runtime_type=self._selection.runtime_type,
            effective_network_mode=self._selection.effective_network_mode,
            network_policy_verified=self._selection.network_policy_verified,
            explicit_local=self._selection.explicit_local,
            budget=ExecutionBudget(),
        )
        return self._filter.decide(request).to_mapping()


def _json_output(payload: Mapping[str, Any]) -> None:
    """输出稳定 JSON，避免 CLI 结果混入路径、异常原文或非结构化日志。"""

    print(json.dumps(dict(payload), ensure_ascii=False, sort_keys=True))


def _fixture_payload(name: str) -> FixturePayload:
    """从受控 fixture 目录解析 diff 或 JSON 载荷，为 D3 完整 fixture 集预留单一入口。"""

    if not name or Path(name).name != name:
        raise CliError("fixture_name_invalid")
    fixture_dir = _PROJECT_ROOT / "tests" / "fixtures" / "diffs"
    diff_path = fixture_dir / f"{name}.diff"
    json_path = fixture_dir / f"{name}.json"
    if diff_path.is_file():
        return FixturePayload(payload_type="diff", diff_text=diff_path.read_text(encoding="utf-8"))
    if json_path.is_file():
        try:
            payload = json.loads(json_path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise CliError("fixture_payload_invalid") from exc
        if isinstance(payload, dict) and isinstance(payload.get("diff"), str):
            return FixturePayload(payload_type="diff", diff_text=payload["diff"])
    raise CliError("fixture_not_found")


def _normalized_files(values: Sequence[str], input_root: Path) -> tuple[Path, ...]:
    """把 CLI 文件实参规范为 input_root 内相对路径，拒绝宿主路径逃逸。"""

    normalized: list[Path] = []
    resolved_root = input_root.resolve()
    for value in values:
        candidate = Path(value)
        if candidate.is_absolute():
            try:
                candidate = candidate.resolve().relative_to(resolved_root)
            except (OSError, ValueError) as exc:
                raise CliError("input_path_outside_root") from exc
        normalized.append(candidate)
    return tuple(normalized)


def _container_available() -> bool:
    """在启动任务前检查严格默认 container 的最小本机前置，缺失时不伪造 local 回退。"""

    executable = shutil.which("docker")
    if executable is None:
        return False
    try:
        result = subprocess.run(
            [executable, "version", "--format", "{{.Server.Version}}"],
            check=False,
            capture_output=True,
            timeout=5,
        )
    except (OSError, subprocess.TimeoutExpired):
        return False
    return result.returncode == 0


def _build_pipeline(args: argparse.Namespace) -> tuple[ReviewPipeline, SqlReviewStore]:
    """按明确 sandbox 选择组装唯一 ReviewPipeline，不让 dry-run 改变隔离策略。"""

    config = ReviewConfig.from_env()
    output_dir = Path(args.output_dir)
    if args.sandbox == "container" and not _container_available():
        raise CliError("container_runtime_unavailable")
    try:
        selection = create_sandbox_runtime(
            args.sandbox,
            explicit_local=args.sandbox == "local",
            local_work_root=str(output_dir / ".workspaces"),
        )
    except SandboxConfigurationError as exc:
        raise CliError("sandbox_configuration_invalid") from exc

    model_environment = None
    if args.model_mode == "real" and not args.dry_run:
        model_environment = load_model_environment(_PROJECT_ROOT / ".env")
    store = SqlReviewStore(args.db_url)
    sandbox = SdkSkillSandbox(selection, _SKILL_ROOT, config=config)
    pipeline = ReviewPipeline(
        store=store,
        governance=PipelineGovernance(
            selection=selection,
            config=config,
            workspace_root=output_dir / ".workspace-root",
        ),
        sandbox=sandbox,
        output_dir=output_dir,
        config=config,
        model_mode="fake" if args.dry_run else args.model_mode,
        model_environment=model_environment,
    )
    return pipeline, store


def _review_input(args: argparse.Namespace) -> dict[str, Any]:
    """将 argparse 输入转换为 pipeline 的四选一输入契约，并保留 fixture 解析边界。"""

    if args.diff_file is not None:
        return {"diff_file": Path(args.diff_file)}
    if args.repo_path is not None:
        return {"repo_path": Path(args.repo_path)}
    if args.files:
        input_root = Path(args.input_root).resolve()
        return {
            "files": _normalized_files(args.files, input_root),
            "input_root": input_root,
        }
    if args.fixture is not None:
        return {"fixture": _fixture_payload(args.fixture)}
    raise CliError("review_input_required")


def _severity_exit_code(report: Mapping[str, Any], threshold: str | None) -> int:
    """仅根据 canonical 正式 findings 和显式阈值决定评审命令的 0 或 1。"""

    if threshold is None:
        return 0
    minimum = _SEVERITY_RANK[threshold]
    for finding in report.get("findings", ()):  # needs_human_review 不得改变 CI 失败语义。
        if isinstance(finding, Mapping) and _SEVERITY_RANK.get(finding.get("severity"), 0) >= minimum:
            return 1
    return 0


def _review(args: argparse.Namespace) -> int:
    """运行唯一评审链路并输出不含原始输入的任务标识、状态和相对报告文件名。"""

    pipeline, store = _build_pipeline(args)
    try:
        result = pipeline.run(**_review_input(args))
        _json_output(
            {
                "task_id": result.task_id,
                "status": result.status,
                "report_files": {
                    "json": "review_report.json",
                    "markdown": "review_report.md",
                },
                "dry_run": bool(args.dry_run),
                "sandbox": args.sandbox,
            }
        )
        return _severity_exit_code(result.report, args.fail_on_severity)
    except PipelineFatalError as exc:
        raise CliError("review_pipeline_failed") from exc
    finally:
        store.close()


def _show(args: argparse.Namespace) -> int:
    """按 task id 查询完整脱敏数据库 bundle；不存在时以退出码 2 表达无效请求。"""

    store = SqlReviewStore(args.db_url)
    try:
        store.initialize()
        bundle = store.get_task_bundle(args.task_id)
    finally:
        store.close()
    if bundle is None:
        raise CliError("task_not_found")
    _json_output(bundle)
    return 0


def _list(args: argparse.Namespace) -> int:
    """列出任务的最小安全摘要，避免将报告、原始输入或宿主路径复制到标准输出。"""

    store = SqlReviewStore(args.db_url)
    try:
        store.initialize()
        payload = {"tasks": store.list_task_summaries()}
    finally:
        store.close()
    _json_output(payload)
    return 0


def _init_db(args: argparse.Namespace) -> int:
    """初始化指定数据库的五张业务表，保持该子命令幂等。"""

    init_db(args.db_url)
    _json_output({"status": "initialized"})
    return 0


def _add_db_argument(parser: argparse.ArgumentParser) -> None:
    """向子命令添加可替换 SQL 后端的 URL 参数，默认保持 SQLite 开箱即用。"""

    parser.add_argument("--db-url", default=DEFAULT_DB_URL)


def _build_parser() -> argparse.ArgumentParser:
    """构建仅暴露本期允许参数的四子命令解析器，未知高风险参数由 argparse 拒绝。"""

    parser = argparse.ArgumentParser(description="Automatic code-review Agent")
    subcommands = parser.add_subparsers(dest="command", required=True)

    review = subcommands.add_parser("review", help="run one deterministic review")
    inputs = review.add_mutually_exclusive_group(required=True)
    inputs.add_argument("--diff-file")
    inputs.add_argument("--repo-path")
    inputs.add_argument("--files", nargs="+")
    inputs.add_argument("--fixture")
    review.add_argument("--input-root", default=str(Path.cwd()))
    review.add_argument("--output-dir", default="out")
    review.add_argument("--sandbox", choices=("container", "cube", "local"), default="container")
    review.add_argument("--dry-run", action="store_true")
    review.add_argument("--model-mode", choices=("fake", "real", "off"), default="fake")
    review.add_argument("--fail-on-severity", choices=tuple(_SEVERITY_RANK))
    _add_db_argument(review)
    review.set_defaults(handler=_review)

    show = subcommands.add_parser("show", help="show one persisted review bundle")
    show.add_argument("task_id")
    _add_db_argument(show)
    show.set_defaults(handler=_show)

    list_command = subcommands.add_parser("list", help="list persisted review tasks")
    _add_db_argument(list_command)
    list_command.set_defaults(handler=_list)

    initialize = subcommands.add_parser("init-db", help="initialize the review database")
    _add_db_argument(initialize)
    initialize.set_defaults(handler=_init_db)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """分发 CLI 子命令并将可预期错误收敛为 2，其他异常不暴露原始运行环境信息。"""

    logging.disable(logging.CRITICAL)
    parser = _build_parser()
    args = parser.parse_args(argv)
    try:
        return int(args.handler(args))
    except (CliError, ValueError):
        _json_output({"status": "invalid", "error": "invalid_request_or_configuration"})
        return 2
    except Exception:
        _json_output({"status": "failed", "error": "review_runtime_error"})
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
