#
# Tencent is pleased to support the open source community by making trpc-agent-python available.
#
# Copyright (C) 2026 Tencent. All rights reserved.
#
# trpc-agent-python is licensed under the Apache License Version 2.0.
#

"""Controlled input acquisition for the code-review pipeline.

Raw diff and source text are intentionally confined to this module's return
object.  Callers must stage the minimal result into a task workspace and must
not log ``ChangeSet.full_text`` or the original input bytes.
"""

from __future__ import annotations

import hashlib
import subprocess
from dataclasses import dataclass, replace
from pathlib import Path
from typing import TYPE_CHECKING, Callable, Mapping, Sequence, Tuple

from .config import ReviewConfig

if TYPE_CHECKING:
    from lib.diff_parser import ChangeSet


_PROJECT_ROOT = Path(__file__).resolve().parents[1]
_SCRIPTS_ROOT = _PROJECT_ROOT / "skills" / "code-review" / "scripts"
_IGNORED_REPO_PARTS = frozenset(
    {
        ".git",
        ".venv",
        "venv",
        "node_modules",
        "build",
        "dist",
        "__pycache__",
        ".tox",
        ".mypy_cache",
        ".pytest_cache",
    }
)
_REPARSE_POINT = 0x0400


class InputValidationError(ValueError):
    """A sanitized invalid-input failure suitable for a warning or CLI error."""


class InputLimitError(InputValidationError):
    """A configured input budget was exceeded before content was staged."""


@dataclass(frozen=True)
class FixturePayload:
    """An explicitly typed fixture payload supplied by a trusted resolver."""

    payload_type: str
    diff_text: str | None = None
    file_contents: Mapping[str, str] | None = None

    def __post_init__(self) -> None:
        if self.payload_type == "diff" and self.diff_text is not None and self.file_contents is None:
            return
        if self.payload_type == "files" and self.file_contents is not None and self.diff_text is None:
            return
        raise InputValidationError("fixture_payload_type_invalid")


@dataclass(frozen=True)
class InputResult:
    """One parsed input plus sanitized acquisition warnings."""

    change_set: "ChangeSet"
    warnings: Tuple[str, ...] = ()


FixtureResolver = Callable[[str], FixturePayload]


def _diff_parser():
    """Import the Skill-owned parsing implementation without duplicating it."""

    import sys

    scripts_root = str(_SCRIPTS_ROOT)
    if scripts_root not in sys.path:
        sys.path.insert(0, scripts_root)
    from lib.diff_parser import build_snapshot_change_set, parse_unified_diff

    return build_snapshot_change_set, parse_unified_diff


def _is_link_or_junction(path: Path) -> bool:
    """Detect POSIX symlinks and Windows reparse points before reading them."""

    try:
        status = path.lstat()
    except OSError:
        return False
    return path.is_symlink() or bool(getattr(status, "st_file_attributes", 0) & _REPARSE_POINT)


def _resolved_root(input_root: Path | None) -> Path:
    root = Path.cwd() if input_root is None else Path(input_root)
    if _is_link_or_junction(root):
        raise InputValidationError("input_root_link_rejected")
    try:
        resolved = root.resolve(strict=True)
    except OSError as exc:
        raise InputValidationError("input_root_unavailable") from exc
    if not resolved.is_dir():
        raise InputValidationError("input_root_not_directory")
    return resolved


def _safe_named_path(path: Path, root: Path, *, allow_absolute: bool = False) -> Path:
    """Validate one explicit input file before its metadata or bytes are read."""

    candidate = Path(path)
    if candidate.is_absolute() and not allow_absolute:
        raise InputValidationError("absolute_input_path_rejected")
    if not candidate.is_absolute():
        if ".." in candidate.parts:
            raise InputValidationError("input_path_traversal_rejected")
        candidate = root / candidate
    try:
        lexical = candidate.relative_to(root)
    except ValueError as exc:
        raise InputValidationError("input_path_outside_root") from exc
    cursor = root
    for part in lexical.parts:
        cursor = cursor / part
        if _is_link_or_junction(cursor):
            raise InputValidationError("input_link_rejected")
    try:
        resolved = candidate.resolve(strict=True)
    except OSError as exc:
        raise InputValidationError("input_path_unavailable") from exc
    try:
        resolved.relative_to(root)
    except ValueError as exc:
        raise InputValidationError("input_path_outside_root") from exc
    if not resolved.is_file():
        raise InputValidationError("input_path_not_regular_file")
    return resolved


def _read_utf8(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError as exc:
        raise InputValidationError("input_text_decode_failed") from exc
    except OSError as exc:
        raise InputValidationError("input_read_failed") from exc


def _read_bytes(path: Path) -> bytes:
    """Read validated input bytes without exposing a host-path exception."""

    try:
        return path.read_bytes()
    except OSError as exc:
        raise InputValidationError("input_read_failed") from exc


def _check_file_limits(paths: Sequence[Path], config: ReviewConfig, *, initial_bytes: int = 0) -> None:
    """Enforce count and byte budgets before any file content is read."""

    if len(paths) > config.max_input_files:
        raise InputLimitError("input_file_count_exceeded")
    total_bytes = initial_bytes
    for path in paths:
        try:
            size = path.stat().st_size
        except OSError as exc:
            raise InputValidationError("input_path_unavailable") from exc
        if size > config.max_input_file_bytes:
            raise InputLimitError("input_file_too_large")
        total_bytes += size
    if total_bytes > config.max_input_bytes:
        raise InputLimitError("input_total_too_large")


def _check_diff_limits(diff_text: str, config: ReviewConfig) -> None:
    encoded = diff_text.encode("utf-8")
    if len(encoded) > config.max_input_file_bytes:
        raise InputLimitError("input_file_too_large")
    if len(encoded) > config.max_input_bytes:
        raise InputLimitError("input_total_too_large")
    if diff_text.count("\n") + 1 > config.max_diff_lines:
        raise InputLimitError("input_diff_lines_exceeded")


def _load_diff_file(diff_file: Path, input_root: Path | None, config: ReviewConfig) -> InputResult:
    root = _resolved_root(input_root)
    path = _safe_named_path(diff_file, root, allow_absolute=True)
    _check_file_limits((path,), config)
    diff_text = _read_utf8(path)
    _check_diff_limits(diff_text, config)
    _, parse_unified_diff = _diff_parser()
    return InputResult(change_set=parse_unified_diff(diff_text, source_kind="diff_file"))


def _load_files(files: Sequence[Path], input_root: Path | None, config: ReviewConfig) -> InputResult:
    root = _resolved_root(input_root)
    paths = tuple(_safe_named_path(Path(path), root) for path in files)
    if len({path.as_posix() for path in paths}) != len(paths):
        raise InputValidationError("input_files_not_unique")
    _check_file_limits(paths, config)
    contents: dict[str, str] = {}
    warnings = []
    for path in paths:
        raw = _read_bytes(path)
        if b"\0" in raw:
            warnings.append("input_binary_skipped")
            continue
        try:
            text = raw.decode("utf-8")
        except UnicodeDecodeError:
            warnings.append("input_non_text_skipped")
            continue
        contents[path.relative_to(root).as_posix()] = text
    build_snapshot_change_set, _ = _diff_parser()
    return InputResult(
        change_set=build_snapshot_change_set(contents, source_kind="files"),
        warnings=tuple(warnings),
    )


def _run_git(repo: Path, *arguments: str) -> str:
    """Run Git with an argv list and return text without surfacing raw stderr."""

    try:
        completed = subprocess.run(
            ["git", "-C", str(repo), *arguments],
            check=True,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=15,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise InputValidationError("git_input_unavailable") from exc
    return completed.stdout


def _repository_root(repo_path: Path) -> Path:
    candidate = Path(repo_path)
    if _is_link_or_junction(candidate):
        raise InputValidationError("repo_link_rejected")
    try:
        resolved = candidate.resolve(strict=True)
    except OSError as exc:
        raise InputValidationError("repo_path_unavailable") from exc
    if not resolved.is_dir():
        raise InputValidationError("repo_path_not_directory")
    git_root = Path(_run_git(resolved, "rev-parse", "--show-toplevel").strip())
    if _is_link_or_junction(git_root):
        raise InputValidationError("repo_link_rejected")
    try:
        return git_root.resolve(strict=True)
    except OSError as exc:
        raise InputValidationError("repo_path_unavailable") from exc


def _repo_file_path(repo: Path, normalized_path: str) -> Path | None:
    relative = Path(normalized_path)
    if relative.is_absolute() or ".." in relative.parts:
        return None
    candidate = repo / relative
    if _is_link_or_junction(candidate):
        return None
    try:
        resolved = candidate.resolve(strict=True)
        resolved.relative_to(repo)
    except (OSError, ValueError):
        return None
    return resolved if resolved.is_file() else None


def _is_ignored_repo_path(relative_path: str) -> bool:
    path = Path(relative_path)
    return any(part in _IGNORED_REPO_PARTS or part.endswith(".egg-info") for part in path.parts)


def _repo_digest(diff_text: str, untracked_contents: Mapping[str, str]) -> str:
    hasher = hashlib.sha256(b"code-review-repo-v1\0")
    diff_bytes = diff_text.encode("utf-8")
    hasher.update(len(diff_bytes).to_bytes(8, "big"))
    hasher.update(diff_bytes)
    for path in sorted(untracked_contents):
        path_bytes = path.encode("utf-8")
        content_bytes = untracked_contents[path].encode("utf-8")
        hasher.update(len(path_bytes).to_bytes(8, "big"))
        hasher.update(path_bytes)
        hasher.update(len(content_bytes).to_bytes(8, "big"))
        hasher.update(content_bytes)
    return hasher.hexdigest()


def _load_repository(repo_path: Path, config: ReviewConfig) -> InputResult:
    repo = _repository_root(repo_path)
    diff_text = _run_git(repo, "diff", "HEAD")
    _check_diff_limits(diff_text, config)
    build_snapshot_change_set, parse_unified_diff = _diff_parser()
    parsed = parse_unified_diff(diff_text, source_kind="repo_path")
    warnings = []
    tracked_paths: list[tuple[int, Path]] = []
    for index, file_change in enumerate(parsed.files):
        if file_change.is_binary or file_change.status == "deleted":
            continue
        path = _repo_file_path(repo, file_change.normalized_path)
        if path is None:
            warnings.append("input_path_skipped")
            continue
        tracked_paths.append((index, path))

    untracked_names = [
        name
        for name in _run_git(repo, "ls-files", "--others", "--exclude-standard").splitlines()
        if name and not _is_ignored_repo_path(name)
    ]
    untracked_paths: list[tuple[str, Path]] = []
    for name in sorted(untracked_names):
        path = _repo_file_path(repo, name)
        if path is None:
            warnings.append("input_path_skipped")
            continue
        untracked_paths.append((name.replace("\\", "/"), path))

    _check_file_limits(
        tuple(path for _, path in tracked_paths) + tuple(path for _, path in untracked_paths),
        config,
        initial_bytes=len(diff_text.encode("utf-8")),
    )

    files = list(parsed.files)
    parse_warnings = list(parsed.parse_warnings)
    for index, path in tracked_paths:
        raw = _read_bytes(path)
        if b"\0" in raw:
            warnings.append("input_binary_skipped")
            continue
        try:
            text = raw.decode("utf-8")
        except UnicodeDecodeError:
            warnings.append("input_non_text_skipped")
            continue
        snapshot = build_snapshot_change_set({files[index].normalized_path: text})
        snapshot_file = snapshot.files[0]
        files[index] = replace(
            files[index],
            full_text=snapshot_file.full_text,
            analysis_mode=snapshot_file.analysis_mode,
        )
        parse_warnings.extend(snapshot.parse_warnings)

    untracked_contents: dict[str, str] = {}
    for name, path in untracked_paths:
        raw = _read_bytes(path)
        if b"\0" in raw:
            warnings.append("input_binary_skipped")
            continue
        try:
            untracked_contents[name] = raw.decode("utf-8")
        except UnicodeDecodeError:
            warnings.append("input_non_text_skipped")
    if untracked_contents:
        snapshots = build_snapshot_change_set(untracked_contents)
        files.extend(replace(file_change, status="added") for file_change in snapshots.files)
        parse_warnings.extend(snapshots.parse_warnings)

    change_set = replace(
        parsed,
        files=tuple(files),
        input_sha256=_repo_digest(diff_text, untracked_contents),
        file_count=len(files),
        hunk_count=sum(len(file_change.hunks) for file_change in files),
        additions=sum(len(file_change.new_changed_lines) for file_change in files),
        deletions=sum(len(file_change.old_changed_lines) for file_change in files),
        parse_warnings=tuple(parse_warnings),
    )
    return InputResult(change_set=change_set, warnings=tuple(warnings))


def _load_fixture(payload: FixturePayload, config: ReviewConfig) -> InputResult:
    build_snapshot_change_set, parse_unified_diff = _diff_parser()
    if payload.payload_type == "diff":
        assert payload.diff_text is not None
        _check_diff_limits(payload.diff_text, config)
        return InputResult(change_set=parse_unified_diff(payload.diff_text, source_kind="fixture"))
    assert payload.file_contents is not None
    encoded_files = tuple(content.encode("utf-8") for content in payload.file_contents.values())
    if len(encoded_files) > config.max_input_files:
        raise InputLimitError("input_file_count_exceeded")
    if any(len(content) > config.max_input_file_bytes for content in encoded_files):
        raise InputLimitError("input_file_too_large")
    if sum(len(content) for content in encoded_files) > config.max_input_bytes:
        raise InputLimitError("input_total_too_large")
    return InputResult(change_set=build_snapshot_change_set(payload.file_contents, source_kind="fixture"))


def load_input(
    *,
    diff_file: Path | None = None,
    repo_path: Path | None = None,
    files: Sequence[Path] | None = None,
    fixture: FixturePayload | str | None = None,
    fixture_resolver: FixtureResolver | None = None,
    input_root: Path | None = None,
    config: ReviewConfig | None = None,
) -> InputResult:
    """Load exactly one supported review input through the secure staging boundary."""

    active_config = ReviewConfig() if config is None else config
    file_list = tuple(files or ())
    selections = (diff_file is not None, repo_path is not None, bool(file_list), fixture is not None)
    if sum(selections) != 1:
        raise InputValidationError("exactly_one_input_required")
    if diff_file is not None:
        return _load_diff_file(Path(diff_file), input_root, active_config)
    if repo_path is not None:
        return _load_repository(Path(repo_path), active_config)
    if file_list:
        return _load_files(file_list, input_root, active_config)
    if isinstance(fixture, str):
        if fixture_resolver is None:
            raise InputValidationError("fixture_resolver_required")
        fixture = fixture_resolver(fixture)
    if not isinstance(fixture, FixturePayload):
        raise InputValidationError("fixture_payload_invalid")
    return _load_fixture(fixture, active_config)
