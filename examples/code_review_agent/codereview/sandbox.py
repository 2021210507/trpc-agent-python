#
# Tencent is pleased to support the open source community by making trpc-agent-python available.
#
# Copyright (C) 2026 Tencent. All rights reserved.
#
# trpc-agent-python is licensed under the Apache License Version 2.0.
#

"""Strict SDK workspace factory, Skill staging and bounded sandbox primitives."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from trpc_agent_sdk.code_executors import BaseWorkspaceRuntime
from trpc_agent_sdk.code_executors import WorkspaceInfo
from trpc_agent_sdk.code_executors import WorkspaceOutputSpec
from trpc_agent_sdk.code_executors import WorkspaceRunProgramSpec
from trpc_agent_sdk.code_executors import create_container_workspace_runtime
from trpc_agent_sdk.code_executors import create_local_workspace_runtime
from trpc_agent_sdk.skills import create_default_skill_repository
from trpc_agent_sdk.skills.stager import SkillStageRequest
from trpc_agent_sdk.skills.tools import CopySkillStager

from codereview.config import ReviewConfig
from codereview.redaction import redact_text


_SKILL_NAME = "code-review"
_RUN_CHECKS_SCRIPT_ID = "run_checks"
_ALLOWED_CONTAINER_CONFIG_KEYS = frozenset({"network_mode"})


class SandboxConfigurationError(ValueError):
    """表示在创建 runtime 前发现的不可接受沙箱配置。"""


class SandboxBudgetExceeded(ValueError):
    """表示本次运行会在启动前突破锁定的评审资源预算。"""


class SandboxStageError(RuntimeError):
    """表示 Skill staging 或 staging 后摘要复验失败。"""


@dataclass(frozen=True)
class SandboxRuntimeSelection:
    """描述已选 SDK runtime 及其可供治理层验证的有效网络配置。"""

    runtime: BaseWorkspaceRuntime
    runtime_type: str
    effective_network_mode: str | None
    network_policy_verified: bool
    explicit_local: bool


@dataclass(frozen=True)
class BudgetReservation:
    """保存一次已经通过预检的运行编号、时间和输出额度。"""

    run_number: int
    timeout_seconds: int
    output_bytes: int


@dataclass(frozen=True)
class OutputCapture:
    """保存受总字节上限约束的 stdout/stderr 摘要及截断标记。"""

    stdout: str
    stderr: str
    truncated: bool


@dataclass(frozen=True)
class SandboxRunCapture:
    """收敛 SDK 单次运行的超时、退出码、耗时和已限额输出摘要。"""

    exit_code: int | None
    timed_out: bool
    duration_ms: int
    output: OutputCapture


@dataclass(frozen=True)
class StagedSkill:
    """记录已复验的 workspace 相对 Skill 目录和入口脚本路径。"""

    workspace_skill_dir: str
    entrypoint: str
    script_id: str
    sha256: str


class SandboxBudget:
    """在宿主启动 runtime 前集中预检并累计单次与全局沙箱预算。"""

    def __init__(self, config: ReviewConfig) -> None:
        """绑定不可变 ReviewConfig，避免调用方单独放宽运行资源上限。"""

        self._config = config
        self._runs_started = 0
        self._reserved_seconds = 0
        self._reserved_output_bytes = 0

    def reserve(self, *, timeout_seconds: int, output_bytes: int) -> BudgetReservation:
        """预留一次运行额度；超过任一锁定上限时在执行前抛出受控错误代码。"""

        if (
            isinstance(timeout_seconds, bool)
            or not isinstance(timeout_seconds, int)
            or timeout_seconds <= 0
            or isinstance(output_bytes, bool)
            or not isinstance(output_bytes, int)
            or output_bytes <= 0
        ):
            raise SandboxBudgetExceeded("sandbox_budget_invalid")
        if timeout_seconds > self._config.per_run_timeout_seconds:
            raise SandboxBudgetExceeded("sandbox_timeout_budget_exceeded")
        if output_bytes > self._config.max_output_bytes_per_run:
            raise SandboxBudgetExceeded("sandbox_output_budget_exceeded")
        if self._runs_started + 1 > self._config.max_sandbox_runs:
            raise SandboxBudgetExceeded("sandbox_run_budget_exceeded")
        if self._reserved_seconds + timeout_seconds > self._config.sandbox_time_budget_seconds:
            raise SandboxBudgetExceeded("sandbox_time_budget_exceeded")
        if self._reserved_output_bytes + output_bytes > self._config.max_output_bytes_per_review:
            raise SandboxBudgetExceeded("sandbox_review_output_budget_exceeded")
        self._runs_started += 1
        self._reserved_seconds += timeout_seconds
        self._reserved_output_bytes += output_bytes
        return BudgetReservation(
            run_number=self._runs_started,
            timeout_seconds=timeout_seconds,
            output_bytes=output_bytes,
        )


def create_sandbox_runtime(
    runtime_type: str = "container",
    *,
    host_config: Mapping[str, Any] | None = None,
    explicit_local: bool = False,
    local_work_root: str = "",
    container_runtime_factory: Callable[..., BaseWorkspaceRuntime] = create_container_workspace_runtime,
    local_runtime_factory: Callable[..., BaseWorkspaceRuntime] = create_local_workspace_runtime,
    cube_runtime_factory: Callable[[], BaseWorkspaceRuntime] | None = None,
) -> SandboxRuntimeSelection:
    """创建 SDK workspace runtime，并把有效网络配置显式交给治理层复验。"""

    if runtime_type == "container":
        effective_config = _strict_container_host_config(host_config)
        runtime = container_runtime_factory(host_config=effective_config)
        return SandboxRuntimeSelection(
            runtime=runtime,
            runtime_type="container",
            effective_network_mode="none",
            network_policy_verified=True,
            explicit_local=False,
        )
    if runtime_type == "local":
        if not explicit_local:
            raise SandboxConfigurationError("local_runtime_not_explicit")
        runtime = local_runtime_factory(
            work_root=local_work_root,
            read_only_staged_skill=True,
            auto_inputs=False,
        )
        return SandboxRuntimeSelection(
            runtime=runtime,
            runtime_type="local",
            effective_network_mode=None,
            network_policy_verified=False,
            explicit_local=True,
        )
    if runtime_type == "cube":
        if cube_runtime_factory is None:
            raise SandboxConfigurationError("cube_runtime_unavailable")
        return SandboxRuntimeSelection(
            runtime=cube_runtime_factory(),
            runtime_type="cube",
            effective_network_mode=None,
            network_policy_verified=False,
            explicit_local=False,
        )
    raise SandboxConfigurationError("sandbox_runtime_unsupported")


def build_sandbox_environment() -> dict[str, str]:
    """构造最小白名单环境，不透传宿主 API Key、token 或任意现有环境变量。"""

    return {
        "LANG": "C.UTF-8",
        "LC_ALL": "C.UTF-8",
        "PYTHONUNBUFFERED": "1",
    }


def build_output_spec(config: ReviewConfig) -> WorkspaceOutputSpec:
    """为单一 findings 文件构造 SDK 声明式输出收集限额。"""

    return WorkspaceOutputSpec(
        globs=["out/findings.json"],
        max_files=1,
        max_file_bytes=config.max_output_bytes_per_run,
        max_total_bytes=config.max_output_bytes_per_run,
        save=False,
        inline=True,
    )


def build_run_spec(staged_skill: StagedSkill, config: ReviewConfig) -> WorkspaceRunProgramSpec:
    """构造固定 run_checks argv、白名单环境和每次运行超时，绝不接收 shell 字符串。"""

    return WorkspaceRunProgramSpec(
        cmd="python3",
        args=["scripts/run_checks.py"],
        env=build_sandbox_environment(),
        cwd=staged_skill.workspace_skill_dir,
        timeout=config.per_run_timeout_seconds,
    )


async def stage_code_review_skill(
    runtime: BaseWorkspaceRuntime,
    workspace: WorkspaceInfo,
    skill_root: Path,
    *,
    script_id: str = _RUN_CHECKS_SCRIPT_ID,
) -> StagedSkill:
    """经 SDK SkillRepository 与 CopySkillStager 复制 Skill，并在沙箱内复验入口摘要。"""

    resolved_root = _validate_skill_root(skill_root)
    repository = create_default_skill_repository(
        str(resolved_root.parent),
        workspace_runtime=runtime,
        enable_hot_reload=False,
        use_cached_repository=False,
    )
    try:
        repository_root = Path(repository.path(_SKILL_NAME)).resolve()
    except (OSError, ValueError) as exc:
        raise SandboxStageError("skill_repository_lookup_failed") from exc
    if repository_root != resolved_root:
        raise SandboxStageError("skill_repository_root_mismatch")

    try:
        result = await CopySkillStager().stage_skill(
            SkillStageRequest(
                skill_name=_SKILL_NAME,
                repository=repository,
                workspace=workspace,
                ctx=None,  # SDK runtime APIs explicitly accept an optional invocation context.
            )
        )
    except Exception as exc:
        raise SandboxStageError("skill_stage_failed") from exc

    entrypoint, expected_sha256 = _manifest_entry(resolved_root, script_id)
    workspace_entrypoint = f"{result.workspace_skill_dir}/scripts/{entrypoint}"
    try:
        collected = await runtime.fs(None).collect(workspace, [workspace_entrypoint], None)
    except Exception as exc:
        raise SandboxStageError("staged_script_collect_failed") from exc
    if len(collected) != 1 or collected[0].name != workspace_entrypoint:
        raise SandboxStageError("staged_script_missing")
    actual_sha256 = hashlib.sha256(collected[0].content.encode("utf-8")).hexdigest()
    if actual_sha256 != expected_sha256:
        raise SandboxStageError("staged_script_integrity_mismatch")
    return StagedSkill(
        workspace_skill_dir=result.workspace_skill_dir,
        entrypoint=workspace_entrypoint,
        script_id=script_id,
        sha256=actual_sha256,
    )


def bounded_output(stdout: str, stderr: str, *, max_bytes: int) -> OutputCapture:
    """按总字节额度截断 stdout/stderr，避免 UTF-8 半字符和无界日志占用。"""

    if isinstance(max_bytes, bool) or not isinstance(max_bytes, int) or max_bytes <= 0:
        raise ValueError("sandbox_output_limit_invalid")
    bounded_stdout, stdout_truncated = _truncate_utf8(stdout, max_bytes)
    remaining = max_bytes - len(bounded_stdout.encode("utf-8"))
    bounded_stderr, stderr_truncated = _truncate_utf8(stderr, remaining)
    return OutputCapture(
        stdout=bounded_stdout,
        stderr=bounded_stderr,
        truncated=stdout_truncated or stderr_truncated,
    )


def capture_workspace_run(result: Any, *, max_output_bytes: int) -> SandboxRunCapture:
    """从 SDK 运行结果提取最小运行事实，并在进入宿主后续处理前执行输出限额。"""

    raw_stdout = getattr(result, "stdout", "")
    raw_stderr = getattr(result, "stderr", "")
    output = bounded_output(
        redact_text(raw_stdout) if isinstance(raw_stdout, str) else "",
        redact_text(raw_stderr) if isinstance(raw_stderr, str) else "",
        max_bytes=max_output_bytes,
    )
    duration = getattr(result, "duration", 0.0)
    duration_ms = max(int(float(duration) * 1000), 0) if isinstance(duration, (int, float)) else 0
    exit_code = getattr(result, "exit_code", None)
    if isinstance(exit_code, bool) or not isinstance(exit_code, int):
        exit_code = None
    return SandboxRunCapture(
        exit_code=exit_code,
        timed_out=bool(getattr(result, "timed_out", False)),
        duration_ms=duration_ms,
        output=output,
    )


def _strict_container_host_config(host_config: Mapping[str, Any] | None) -> dict[str, Any]:
    """拒绝 bind、未知字段和 network_mode 覆盖，确保容器实例有效网络配置为 none。"""

    supplied = {} if host_config is None else dict(host_config)
    if "Binds" in supplied or "binds" in supplied or "volumes" in supplied:
        raise SandboxConfigurationError("host_mount_forbidden")
    unknown = set(supplied) - _ALLOWED_CONTAINER_CONFIG_KEYS
    if unknown:
        raise SandboxConfigurationError("container_host_config_unsupported")
    if supplied.get("network_mode", "none") != "none":
        raise SandboxConfigurationError("container_network_mode_invalid")
    return {"network_mode": "none"}


def _validate_skill_root(skill_root: Path) -> Path:
    """验证 host Skill 根目录是规范 code-review 目录，防止 staging 任意宿主路径。"""

    try:
        resolved_root = Path(skill_root).resolve(strict=True)
    except OSError as exc:
        raise SandboxStageError("skill_root_unavailable") from exc
    if resolved_root.name != _SKILL_NAME or not (resolved_root / "SKILL.md").is_file():
        raise SandboxStageError("skill_root_invalid")
    return resolved_root


def _manifest_entry(skill_root: Path, script_id: str) -> tuple[str, str]:
    """从受控 manifest 提取一个已注册入口及其 SHA-256，不接受外部命令文本。"""

    try:
        manifest = json.loads((skill_root / "scripts" / "manifest.json").read_text(encoding="utf-8"))
    except (OSError, ValueError, UnicodeDecodeError) as exc:
        raise SandboxStageError("manifest_unavailable") from exc
    scripts = manifest.get("scripts") if isinstance(manifest, Mapping) else None
    if not isinstance(scripts, list):
        raise SandboxStageError("manifest_invalid")
    for item in scripts:
        if not isinstance(item, Mapping) or item.get("script_id") != script_id:
            continue
        entrypoint = item.get("entrypoint")
        sha256 = item.get("sha256")
        relative = Path(entrypoint) if isinstance(entrypoint, str) else None
        if (
            relative is None
            or relative.is_absolute()
            or ".." in relative.parts
            or not isinstance(sha256, str)
            or len(sha256) != 64
        ):
            break
        return relative.as_posix(), sha256
    raise SandboxStageError("manifest_script_unregistered")


def _truncate_utf8(text: str, max_bytes: int) -> tuple[str, bool]:
    """返回不超过字节额度的 UTF-8 前缀，必要时回退到完整字符边界。"""

    if not isinstance(text, str):
        return "", True
    if max_bytes <= 0:
        return "", bool(text)
    encoded = text.encode("utf-8")
    if len(encoded) <= max_bytes:
        return text, False
    prefix = encoded[:max_bytes]
    while prefix:
        try:
            return prefix.decode("utf-8"), True
        except UnicodeDecodeError:
            prefix = prefix[:-1]
    return "", True
