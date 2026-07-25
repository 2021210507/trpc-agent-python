#
# Tencent is pleased to support the open source community by making trpc-agent-python available.
#
# Copyright (C) 2026 Tencent. All rights reserved.
#
# trpc-agent-python is licensed under the Apache License Version 2.0.
#

"""Heuristic security rules that operate only on executable Python code."""

from __future__ import annotations

import io
import re
import tokenize
from dataclasses import dataclass
from typing import Callable, List, Tuple

from .diff_parser import ChangeSet
from .rule_engine import ReviewRule, RuleMatch, SecretRule
from .secret_rules import redact_text


_SQL_KEYWORDS = re.compile(r"\b(?:select|insert|update|delete)\b", re.IGNORECASE)
_INTERPOLATION = re.compile(r"\{[^{}]+\}")
_SHELL_TRUE = re.compile(
    r"\bsubprocess\.(?:run|call|check_call|check_output|Popen)\s*\([^\n]*\bshell\s*=\s*True\b"
)
_DYNAMIC_EVAL = re.compile(r"(?<![.\w])eval\s*\(")
_DYNAMIC_EXEC = re.compile(r"(?<![.\w])exec\s*\(")
_OS_SYSTEM = re.compile(r"\bos\.system\s*\(")


def _mask_non_code(line: str) -> Tuple[str, Tuple[str, ...]]:
    """Remove comments and ordinary strings while retaining f-string tokens."""

    masked = list(line)
    f_strings: List[str] = []
    try:
        tokens = tokenize.generate_tokens(io.StringIO(f"{line}\n").readline)
        for token in tokens:
            if token.type == tokenize.COMMENT:
                start, end = token.start[1], token.end[1]
                masked[start:end] = " " * (end - start)
            elif token.type == tokenize.STRING:
                start, end = token.start[1], token.end[1]
                masked[start:end] = " " * (end - start)
                if token.string.lower().lstrip("rub").startswith("f"):
                    f_strings.append(token.string)
    except (tokenize.TokenError, IndentationError):
        comment_index = line.find("#")
        if comment_index >= 0:
            masked[comment_index:] = " " * (len(line) - comment_index)
    return "".join(masked), tuple(f_strings)


def _advance_triple_quote_state(
    line: str,
    active_delimiter: str | None,
) -> Tuple[str | None, bool]:
    """Suppress whole lines belonging to a triple-quoted string/docstring."""

    if active_delimiter is not None:
        return (
            (None if active_delimiter in line else active_delimiter),
            True,
        )
    if line.lstrip().startswith("#"):
        return None, False
    for delimiter in ('"""', "'''"):
        start = line.find(delimiter)
        if start < 0:
            continue
        end = line.find(delimiter, start + len(delimiter))
        return (None if end >= 0 else delimiter), True
    return None, False


@dataclass(frozen=True)
class SecurityRule:
    """One line-oriented security rule with explicit public metadata."""

    rule_id: str
    severity: str
    confidence: float
    title: str
    recommendation: str
    detector: Callable[[str, Tuple[str, ...]], bool]
    category: str = "security"
    requires_full_file: bool = False

    def match(self, change_set: ChangeSet) -> Tuple[RuleMatch, ...]:
        matches = []
        for file_change in change_set.files:
            if file_change.is_binary or not file_change.normalized_path.endswith(".py"):
                continue
            if file_change.review_scope == "deleted_lines":
                continue
            for hunk in file_change.hunks:
                triple_quote = None
                for line_number, line_text in sorted(hunk.added_lines.items()):
                    triple_quote, is_triple_quoted = _advance_triple_quote_state(
                        line_text,
                        triple_quote,
                    )
                    if is_triple_quoted:
                        continue
                    code, f_strings = _mask_non_code(line_text)
                    if not self.detector(code, f_strings):
                        continue
                    matches.append(
                        RuleMatch(
                            rule_id=self.rule_id,
                            category=self.category,
                            severity=self.severity,
                            confidence=self.confidence,
                            file=file_change.normalized_path,
                            line=line_number,
                            title=self.title,
                            evidence=redact_text(line_text),
                            recommendation=self.recommendation,
                            source="heuristic",
                        )
                    )
        return tuple(matches)


def _sql_fstring(_code: str, f_strings: Tuple[str, ...]) -> bool:
    if any(_SQL_KEYWORDS.search(value) and _INTERPOLATION.search(value) for value in f_strings):
        return True
    return bool(
        re.search(
            r"\bf(?:r|u|b)?(?:'|\").*\b(?:select|insert|update|delete)\b.*\{[^{}]+\}",
            _code,
            re.IGNORECASE,
        )
    )


def _shell_true(code: str, _f_strings: Tuple[str, ...]) -> bool:
    return bool(_SHELL_TRUE.search(code))


def _dynamic_eval(code: str, _f_strings: Tuple[str, ...]) -> bool:
    return bool(_DYNAMIC_EVAL.search(code))


def _dynamic_exec(code: str, _f_strings: Tuple[str, ...]) -> bool:
    return bool(_DYNAMIC_EXEC.search(code))


def _os_system(code: str, _f_strings: Tuple[str, ...]) -> bool:
    return bool(_OS_SYSTEM.search(code))


def default_security_rules() -> Tuple[ReviewRule, ...]:
    """Return the A4 rule pack in deterministic execution order."""

    return (
        SecurityRule(
            rule_id="security.sql-fstring",
            severity="high",
            confidence=0.82,
            title="SQL is built with an interpolated f-string",
            recommendation="Use parameterized queries and bind user-controlled values separately.",
            detector=_sql_fstring,
        ),
        SecurityRule(
            rule_id="security.subprocess-shell-true",
            severity="high",
            confidence=0.85,
            title="subprocess executes with shell=True",
            recommendation="Pass an argument list with shell disabled and validate all command inputs.",
            detector=_shell_true,
        ),
        SecurityRule(
            rule_id="security.dynamic-eval",
            severity="critical",
            confidence=0.85,
            title="Dynamic eval can execute untrusted input",
            recommendation="Replace eval with a strict parser or allowlisted dispatch table.",
            detector=_dynamic_eval,
        ),
        SecurityRule(
            rule_id="security.dynamic-exec",
            severity="critical",
            confidence=0.85,
            title="Dynamic exec can execute untrusted input",
            recommendation="Remove exec and use explicit, allowlisted program behavior.",
            detector=_dynamic_exec,
        ),
        SecurityRule(
            rule_id="security.os-system",
            severity="high",
            confidence=0.85,
            title="os.system invokes a shell command",
            recommendation="Use subprocess with shell disabled and a validated argument list.",
            detector=_os_system,
        ),
        SecretRule(),
    )
