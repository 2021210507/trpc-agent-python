#!/usr/bin/env python3
"""Read-only readiness checks for the automatic code-review Agent QA skill."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[4]
SPEC = REPO_ROOT / "DEV_SPEC.md"
EXAMPLE = REPO_ROOT / "examples" / "code_review_agent"
AUTO_REFS = REPO_ROOT / ".github" / "skills" / "auto-coder" / "references"
SPEC_HASH = REPO_ROOT / ".github" / "skills" / "auto-coder" / ".spec_hash"
PROGRESS = REPO_ROOT / ".github" / "skills" / "qa-tester" / "QA_TEST_PROGRESS.md"
EXPECTED_REFERENCE_NAMES = {
    "01-overview.md",
    "02-features.md",
    "03-tech-stack.md",
    "04-testing.md",
    "05-architecture.md",
    "06-schedule.md",
    "07-future.md",
}
EXPECTED_TEST_LAYERS = ("unit", "integration", "e2e", "fixtures", "support")


def _spec_chapters() -> list[int]:
    if not SPEC.exists():
        return []
    text = SPEC.read_text(encoding="utf-8")
    return [int(value) for value in re.findall(r"^## (\d+)\. ", text, re.MULTILINE)]


def _schedule_counts() -> dict[str, int]:
    counts = {"completed": 0, "in_progress": 0, "pending": 0}
    if not SPEC.exists():
        return counts
    for marker in re.findall(
        r"^\|\s*[A-E]\d+\s*\|.*?\|\s*(\[[ x~]\])\s*\|",
        SPEC.read_text(encoding="utf-8"),
        re.MULTILINE,
    ):
        key = {"[x]": "completed", "[~]": "in_progress", "[ ]": "pending"}[marker]
        counts[key] += 1
    return counts


def _progress_counts() -> dict[str, int]:
    icons = {"✅": "pass", "❌": "fail", "⏭️": "skip", "🔧": "fix", "⬜": "pending"}
    counts = {value: 0 for value in icons.values()}
    if not PROGRESS.exists():
        return counts
    for icon in re.findall(
        r"^\|\s*(✅|❌|⏭️|🔧|⬜)\s*\|\s*[A-H]-\d+\s*\|",
        PROGRESS.read_text(encoding="utf-8"),
        re.MULTILINE,
    ):
        counts[icons[icon]] += 1
    return counts


def _reference_state() -> tuple[list[str], bool]:
    names = {path.name for path in AUTO_REFS.glob("*.md")} if AUTO_REFS.exists() else set()
    missing = sorted(EXPECTED_REFERENCE_NAMES - names)
    if not SPEC.exists() or not SPEC_HASH.exists():
        return missing, False
    expected = hashlib.sha256(SPEC.read_bytes()).hexdigest()
    actual = SPEC_HASH.read_text(encoding="utf-8").strip()
    return missing, expected == actual


def collect() -> dict[str, object]:
    missing_refs, hash_matches = _reference_state()
    tests_root = EXAMPLE / "tests"
    test_layers = {
        name: (tests_root / name).is_dir() for name in EXPECTED_TEST_LAYERS
    }
    venv_python = (
        REPO_ROOT / ".venv" / "Scripts" / "python.exe"
        if sys.platform == "win32"
        else REPO_ROOT / ".venv" / "bin" / "python"
    )
    return {
        "repo_root": str(REPO_ROOT),
        "python": sys.executable,
        "python_version": ".".join(map(str, sys.version_info[:3])),
        "python_supported": sys.version_info >= (3, 10),
        "venv_python_exists": venv_python.exists(),
        "docker_available": shutil.which("docker") is not None,
        "dev_spec_exists": SPEC.exists(),
        "spec_chapters": _spec_chapters(),
        "spec_chapters_valid": _spec_chapters() == list(range(1, 8)),
        "auto_reference_missing": missing_refs,
        "auto_reference_hash_matches": hash_matches,
        "example_exists": EXAMPLE.exists(),
        "tests_exist": tests_root.exists(),
        "test_layers": test_layers,
        "test_layers_valid": all(test_layers.values()),
        "top_level_fixtures_exists": (EXAMPLE / "fixtures").exists(),
        "schedule": _schedule_counts(),
        "qa_progress": _progress_counts(),
    }


def show(data: dict[str, object], as_json: bool) -> None:
    if as_json:
        print(json.dumps(data, ensure_ascii=False, indent=2))
        return
    print("Code Review Agent QA readiness")
    print(f"python_version={data['python_version']}")
    print(f"python_supported={data['python_supported']}")
    print(f"venv_python_exists={data['venv_python_exists']}")
    print(f"docker_available={data['docker_available']}")
    print(f"dev_spec_exists={data['dev_spec_exists']}")
    print(f"spec_chapters={data['spec_chapters']}")
    print(f"spec_chapters_valid={data['spec_chapters_valid']}")
    print(f"auto_reference_missing={data['auto_reference_missing']}")
    print(f"auto_reference_hash_matches={data['auto_reference_hash_matches']}")
    print(f"example_exists={data['example_exists']}")
    print(f"tests_exist={data['tests_exist']}")
    print(f"test_layers={data['test_layers']}")
    print(f"test_layers_valid={data['test_layers_valid']}")
    print(f"top_level_fixtures_exists={data['top_level_fixtures_exists']}")
    print(f"schedule={data['schedule']}")
    print(f"qa_progress={data['qa_progress']}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "command",
        nargs="?",
        choices=("status", "check-spec", "check-ready"),
        default="status",
    )
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    data = collect()
    show(data, args.json)

    if args.command == "status":
        return 0
    spec_ok = bool(
        data["python_supported"]
        and data["dev_spec_exists"]
        and data["spec_chapters_valid"]
        and not data["auto_reference_missing"]
        and data["auto_reference_hash_matches"]
    )
    if args.command == "check-spec":
        return 0 if spec_ok else 1
    ready = spec_ok and bool(
        data["example_exists"]
        and data["tests_exist"]
        and data["test_layers_valid"]
        and not data["top_level_fixtures_exists"]
    )
    return 0 if ready else 1


if __name__ == "__main__":
    raise SystemExit(main())
