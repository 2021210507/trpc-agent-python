#
# Tencent is pleased to support the open source community by making trpc-agent-python available.
#
# Copyright (C) 2026 Tencent. All rights reserved.
#
# trpc-agent-python is licensed under the Apache License Version 2.0.
#

"""Tests for the deterministic rule protocol and security rules."""

from __future__ import annotations

import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_ROOT = PROJECT_ROOT / "skills" / "code-review" / "scripts"
sys.path.insert(0, str(SCRIPTS_ROOT))

from lib.diff_parser import parse_unified_diff  # noqa: E402
from lib.rule_engine import RuleEngine  # noqa: E402
from lib.rules_security import default_security_rules  # noqa: E402


def _added_python_change_set(*lines: str):
    diff_lines = [
        "diff --git a/src/example.py b/src/example.py",
        "new file mode 100644",
        "--- /dev/null",
        "+++ b/src/example.py",
        f"@@ -0,0 +1,{len(lines)} @@",
    ]
    diff_lines.extend(f"+{line}" for line in lines)
    return parse_unified_diff("\n".join(diff_lines))


def _engine() -> RuleEngine:
    return RuleEngine(default_security_rules())


def test_security_rules_expose_protocol_metadata_and_detect_dangerous_code() -> None:
    change_set = _added_python_change_set(
        'query = f"SELECT * FROM users WHERE name = \'{name}\'"',
        "subprocess.run(command, shell=True)",
        "result = eval(user_input)",
        "exec(compiled_code)",
        "os.system(command)",
    )

    matches = _engine().match(change_set)

    assert all(
        rule.rule_id
        and rule.category
        and rule.severity
        and 0.0 <= rule.confidence <= 1.0
        and isinstance(rule.requires_full_file, bool)
        for rule in _engine().rules
    )
    assert [match.rule_id for match in matches] == [
        "security.sql-fstring",
        "security.subprocess-shell-true",
        "security.dynamic-eval",
        "security.dynamic-exec",
        "security.os-system",
    ]
    assert all(match.category == "security" for match in matches)
    assert {match.severity for match in matches} == {"high", "critical"}
    assert all(0.70 <= match.confidence <= 0.85 for match in matches)
    assert all(match.source == "heuristic" for match in matches)
    assert [match.line for match in matches] == [1, 2, 3, 4, 5]
    assert all(match.line_side == "new" for match in matches)


def test_security_rules_ignore_comments_docstrings_and_ordinary_strings() -> None:
    change_set = _added_python_change_set(
        "# subprocess.run(command, shell=True); eval(user_input)",
        'description = "os.system(command); exec(payload)"',
        'documentation = "query = f\'SELECT * FROM users WHERE id = {user_id}\'"',
        '"""eval(user_input); subprocess.run(command, shell=True)"""',
        '"""',
        "exec(payload)",
        '"""',
    )

    matches = _engine().match(change_set)

    assert matches == ()


def test_security_rules_only_report_new_changed_lines() -> None:
    diff = "\n".join(
        [
            "diff --git a/src/example.py b/src/example.py",
            "--- a/src/example.py",
            "+++ b/src/example.py",
            "@@ -10,2 +10,2 @@",
            "-result = eval(user_input)",
            "+result = sanitize(user_input)",
            " context = 'exec(payload)'",
        ]
    )

    assert _engine().match(parse_unified_diff(diff)) == ()


def test_secret_rule_scans_real_format_string_literals_without_structure_filter() -> None:
    token = "ghp_" + "abcdefghijklmnopqrstuvwxyz0123456789"
    change_set = _added_python_change_set(f"GITHUB_TOKEN = '{token}'")

    matches = _engine().match(change_set)

    assert len(matches) == 1
    assert matches[0].rule_id == "secrets.github_token"
    assert matches[0].category == "secrets"
    assert matches[0].line == 1
    assert token not in matches[0].evidence
    assert "[REDACTED:github_token]" in matches[0].evidence
