#!/usr/bin/env python3
"""Validate QA progress counters and current-session execution evidence."""

from __future__ import annotations

import argparse
import re
import sys
from collections import Counter
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[4]
PROGRESS = REPO_ROOT / ".github" / "skills" / "qa-tester" / "QA_TEST_PROGRESS.md"
ICONS = {"✅": "Pass", "❌": "Fail", "⏭️": "Skip", "🔧": "Fix", "⬜": "Pending"}
INFERENCE_PATTERNS = (
    r"(?i)\balready verified\b",
    r"(?i)\bverified (in|via|through) [A-H]-\d+",
    r"(?i)\bsame as\b",
    r"(?i)\bcode (uses|shows|contains)\b",
    r"(?i)\bshould (work|pass|fail)\b",
    r"(?i)\bwould (work|pass|fail|raise)\b",
)
VALUE_PATTERNS = (
    r"\bexit(?:_code)?=-?\d+\b",
    r"\b\d+\s+passed\b",
    r"\b\d+\s+failed\b",
    r"\b\d+\s+skipped\b",
    r"\bduration(?:_ms|_s)?=\d+",
    r"\b(?:count|findings|warnings|plaintext_hits|sandbox_runs|chapters|references)=\d+",
    r"\b(?:status|action|runtime|network_mode|pytest)=[^,\s]+",
    r"\b(?:recall|fp_share|redaction_rate)=\d+(?:\.\d+)?",
)


def parse_rows(text: str) -> list[tuple[str, str, str, int]]:
    rows = []
    pattern = re.compile(
        r"^\|\s*(✅|❌|⏭️|🔧|⬜)\s*\|\s*([A-H]-\d+)\s*\|[^|]*\|\s*(.*?)\s*\|$"
    )
    for line_number, line in enumerate(text.splitlines(), 1):
        match = pattern.match(line)
        if match:
            rows.append((match.group(1), match.group(2), match.group(3).strip(), line_number))
    return rows


def declared_counts(text: str) -> dict[str, int] | None:
    match = re.search(
        r"✅ Pass: (\d+) \| ❌ Fail: (\d+) \| ⏭️ Skip: (\d+) \| 🔧 Fix: (\d+) \| ⬜ Pending: (\d+)",
        text,
    )
    if not match:
        return None
    return dict(zip(("Pass", "Fail", "Skip", "Fix", "Pending"), map(int, match.groups())))


def validate(section: str | None) -> list[str]:
    text = PROGRESS.read_text(encoding="utf-8")
    all_rows = parse_rows(text)
    rows = [row for row in all_rows if section is None or row[1].startswith(section + "-")]
    issues: list[str] = []

    if section is None:
        declared_total_match = re.search(r"> Total: (\d+)", text)
        if not declared_total_match:
            issues.append("Missing total count")
        elif int(declared_total_match.group(1)) != len(all_rows):
            issues.append(
                f"Total mismatch: declared={declared_total_match.group(1)} actual={len(all_rows)}"
            )

        actual = Counter(ICONS[icon] for icon, _, _, _ in all_rows)
        declared = declared_counts(text)
        if declared is None:
            issues.append("Missing summary counters")
        elif any(declared[name] != actual[name] for name in declared):
            issues.append(f"Counter mismatch: declared={declared} actual={dict(actual)}")

    for icon, test_id, note, line_number in rows:
        if icon == "⬜":
            continue
        if not note:
            issues.append(f"{test_id} line {line_number}: completed row has empty note")
            continue
        if any(re.search(pattern, note) for pattern in INFERENCE_PATTERNS):
            issues.append(f"{test_id} line {line_number}: inferred/cross-referenced evidence")
        if icon in {"✅", "❌", "🔧"}:
            if 'command="' not in note:
                issues.append(f"{test_id} line {line_number}: missing command evidence")
            value_count = sum(
                1 for pattern in VALUE_PATTERNS if re.search(pattern, note, re.IGNORECASE)
            )
            if value_count < 2:
                issues.append(
                    f"{test_id} line {line_number}: fewer than two concrete evidence values"
                )
        if icon == "⏭️" and test_id not in {"G-01", "G-02"}:
            issues.append(f"{test_id} line {line_number}: skip allowed only for G-01/G-02")

    return issues


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--section", choices=list("ABCDEFGH"))
    args = parser.parse_args()
    issues = validate(args.section)
    print(f"validated_section={args.section or 'ALL'}")
    print(f"issue_count={len(issues)}")
    for issue in issues:
        print(f"- {issue}")
    return 1 if issues else 0


if __name__ == "__main__":
    raise SystemExit(main())
