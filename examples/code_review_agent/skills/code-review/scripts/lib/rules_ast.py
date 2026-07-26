#
# Tencent is pleased to support the open source community by making trpc-agent-python available.
#
# Copyright (C) 2026 Tencent. All rights reserved.
#
# trpc-agent-python is licensed under the Apache License Version 2.0.
#

"""Full-file AST confirmation for deterministic Python security findings.

The diff parser owns syntax validation and records a sanitized warning when a
complete Python file cannot be parsed.  This module never attempts AST parsing
for hunk-only inputs, deleted files, or parser-downgraded files.  A changed-line
review may only report an AST node that intersects a newly changed line.
"""

from __future__ import annotations

import ast
import re
from dataclasses import dataclass
from typing import List, Tuple

from .diff_parser import ChangeSet
from .rule_engine import ReviewRule, RuleMatch
from .secret_rules import redact_text


_SQL_KEYWORDS = re.compile(r"\b(?:select|insert|update|delete)\b", re.IGNORECASE)


@dataclass(frozen=True)
class _ASTCandidate:
    """One AST-confirmed dangerous construct before review-scope filtering."""

    rule_id: str
    severity: str
    title: str
    start_line: int
    end_line: int


class _SecurityVisitor(ast.NodeVisitor):
    """Collect the A4 security patterns from an already validated AST."""

    def __init__(self) -> None:
        self.candidates: List[_ASTCandidate] = []

    def visit_Call(self, node: ast.Call) -> None:
        self._record_dynamic_code(node)
        self._record_os_system(node)
        self._record_subprocess_shell(node)
        self.generic_visit(node)

    def visit_JoinedStr(self, node: ast.JoinedStr) -> None:
        constants = [
            value.value
            for value in node.values
            if isinstance(value, ast.Constant) and isinstance(value.value, str)
        ]
        if any(_SQL_KEYWORDS.search(value) for value in constants) and any(
            isinstance(value, ast.FormattedValue) for value in node.values
        ):
            self._record(
                node,
                "security.sql-fstring",
                "high",
                "SQL is built with an interpolated f-string",
            )
        self.generic_visit(node)

    def _record_dynamic_code(self, node: ast.Call) -> None:
        if isinstance(node.func, ast.Name) and node.func.id == "eval":
            self._record(
                node,
                "security.dynamic-eval",
                "critical",
                "Dynamic eval can execute untrusted input",
            )
        elif isinstance(node.func, ast.Name) and node.func.id == "exec":
            self._record(
                node,
                "security.dynamic-exec",
                "critical",
                "Dynamic exec can execute untrusted input",
            )

    def _record_os_system(self, node: ast.Call) -> None:
        if (
            isinstance(node.func, ast.Attribute)
            and isinstance(node.func.value, ast.Name)
            and node.func.value.id == "os"
            and node.func.attr == "system"
        ):
            self._record(
                node,
                "security.os-system",
                "high",
                "os.system invokes a shell command",
            )

    def _record_subprocess_shell(self, node: ast.Call) -> None:
        if not (
            isinstance(node.func, ast.Attribute)
            and isinstance(node.func.value, ast.Name)
            and node.func.value.id == "subprocess"
            and node.func.attr in {"run", "call", "check_call", "check_output", "Popen"}
        ):
            return
        if any(
            keyword.arg == "shell"
            and isinstance(keyword.value, ast.Constant)
            and keyword.value.value is True
            for keyword in node.keywords
        ):
            self._record(
                node,
                "security.subprocess-shell-true",
                "high",
                "subprocess executes with shell=True",
            )

    def _record(self, node: ast.AST, rule_id: str, severity: str, title: str) -> None:
        start_line = getattr(node, "lineno", 0)
        end_line = getattr(node, "end_lineno", start_line) or start_line
        self.candidates.append(
            _ASTCandidate(
                rule_id=rule_id,
                severity=severity,
                title=title,
                start_line=start_line,
                end_line=end_line,
            )
        )


def _ast_candidates(full_text: str) -> Tuple[_ASTCandidate, ...]:
    """Parse one complete file defensively and return stable candidates."""

    try:
        tree = ast.parse(full_text)
    except SyntaxError:
        # The parser normally prevents this path and records the warning there.
        return ()
    visitor = _SecurityVisitor()
    visitor.visit(tree)
    return tuple(visitor.candidates)


def _review_line(candidate: _ASTCandidate, review_scope: str, changed_lines: Tuple[int, ...]) -> int | None:
    """Return an in-scope primary location, anchored to a changed line when needed."""

    if review_scope == "full_file":
        return candidate.start_line
    if review_scope != "changed_lines":
        return None
    for line in changed_lines:
        if candidate.start_line <= line <= candidate.end_line:
            return line
    return None


def _source_line(full_text: str, line_number: int) -> str:
    """Return one source line without leaking an out-of-range exception."""

    lines = full_text.splitlines()
    return lines[line_number - 1] if 1 <= line_number <= len(lines) else ""


def _recommendation(rule_id: str) -> str:
    """Return the deterministic remediation for one supported AST rule."""

    recommendations = {
        "security.dynamic-eval": "Replace eval with a strict parser or allowlisted dispatch table.",
        "security.dynamic-exec": "Remove exec and use explicit, allowlisted program behavior.",
        "security.os-system": "Use subprocess with shell disabled and a validated argument list.",
        "security.subprocess-shell-true": "Pass an argument list with shell disabled and validate all command inputs.",
        "security.sql-fstring": "Use parameterized queries and bind user-controlled values separately.",
    }
    return recommendations[rule_id]


@dataclass(frozen=True)
class ASTSecurityRule:
    """AST confirmation for A4 security rules when a complete Python file exists."""

    rule_id: str = "security.ast-confirmation"
    category: str = "security"
    severity: str = "high"
    confidence: float = 0.92
    requires_full_file: bool = True

    def match(self, change_set: ChangeSet) -> Tuple[RuleMatch, ...]:
        matches: List[RuleMatch] = []
        for file_change in change_set.files:
            if file_change.is_binary or not file_change.normalized_path.endswith(".py"):
                continue
            if file_change.review_scope not in {"changed_lines", "full_file"}:
                continue
            if file_change.full_text is None or file_change.analysis_mode != "ast_validated":
                continue
            for candidate in _ast_candidates(file_change.full_text):
                line = _review_line(
                    candidate,
                    file_change.review_scope,
                    file_change.new_changed_lines,
                )
                if line is None:
                    continue
                matches.append(
                    RuleMatch(
                        rule_id=candidate.rule_id,
                        category=self.category,
                        severity=candidate.severity,
                        confidence=self.confidence,
                        file=file_change.normalized_path,
                        line=line,
                        title=candidate.title,
                        evidence=redact_text(_source_line(file_change.full_text, line)),
                        recommendation=_recommendation(candidate.rule_id),
                        source="ast",
                    )
                )
        return tuple(matches)


def default_ast_rules() -> Tuple[ReviewRule, ...]:
    """Return the deterministic A7 full-file rule pack."""

    return (ASTSecurityRule(),)
