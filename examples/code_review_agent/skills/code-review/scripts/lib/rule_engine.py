#
# Tencent is pleased to support the open source community by making trpc-agent-python available.
#
# Copyright (C) 2026 Tencent. All rights reserved.
#
# trpc-agent-python is licensed under the Apache License Version 2.0.
#

"""Standard-library-only deterministic review engine."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, Sequence, Tuple

from .diff_parser import ChangeSet
from .secret_rules import detect_change_set_secrets


_SEVERITIES = frozenset({"critical", "high", "medium", "low", "info"})
_SOURCES = frozenset({"rule-engine", "ast", "heuristic"})


@dataclass(frozen=True)
class RuleMatch:
    """A pre-deduplication, already-redacted deterministic rule result."""

    rule_id: str
    category: str
    severity: str
    confidence: float
    file: str
    line: int
    title: str
    evidence: str
    recommendation: str
    source: str = "rule-engine"
    line_side: str = "new"

    def __post_init__(self) -> None:
        if not self.rule_id or not self.category:
            raise ValueError("rule_id and category must be non-empty")
        if self.severity not in _SEVERITIES:
            raise ValueError("severity is invalid")
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError("confidence must be between 0 and 1")
        if not self.file or self.line < 1:
            raise ValueError("file and line must identify a real source line")
        if self.source not in _SOURCES:
            raise ValueError("source is invalid")
        if self.line_side not in {"new", "old"}:
            raise ValueError("line_side is invalid")


class ReviewRule(Protocol):
    """The plug-in contract shared by all deterministic review rules."""

    rule_id: str
    category: str
    severity: str
    confidence: float
    requires_full_file: bool

    def match(self, change_set: ChangeSet) -> Tuple[RuleMatch, ...]:
        """Return redacted matches for one parsed review input."""


@dataclass(frozen=True)
class SecretRule:
    """Adapt the A3 detector to the common deterministic rule protocol."""

    rule_id: str = "secrets.detect"
    category: str = "secrets"
    severity: str = "high"
    confidence: float = 0.95
    requires_full_file: bool = False

    def match(self, change_set: ChangeSet) -> Tuple[RuleMatch, ...]:
        matches = []
        for location in detect_change_set_secrets(change_set):
            recommendation = (
                "Revoke and rotate the exposed credential, then load it from "
                "a secret manager or protected environment variable."
            )
            if location.line_side == "old":
                recommendation = (
                    "Treat the deleted credential as exposed in history; revoke "
                    "and rotate it, then verify the replacement is managed safely."
                )
            matches.append(
                RuleMatch(
                    rule_id=f"secrets.{location.secret_type}",
                    category=self.category,
                    severity=self.severity,
                    confidence=location.confidence,
                    file=location.file,
                    line=location.line,
                    title="Potential hard-coded secret",
                    evidence=location.evidence,
                    recommendation=recommendation,
                    source="rule-engine",
                    line_side=location.line_side,
                )
            )
        return tuple(matches)


class RuleEngine:
    """Run a stable sequence of rules through one dispatching boundary."""

    def __init__(self, rules: Sequence[ReviewRule]) -> None:
        self._rules = tuple(rules)

    @property
    def rules(self) -> Tuple[ReviewRule, ...]:
        """Expose immutable rule metadata for manifests and diagnostics."""

        return self._rules

    def match(self, change_set: ChangeSet) -> Tuple[RuleMatch, ...]:
        """Dispatch rules and sort findings deterministically before deduplication."""

        matches = []
        for rule in self._rules:
            matches.extend(rule.match(change_set))
        return tuple(
            sorted(
                matches,
                key=lambda item: (
                    item.file,
                    item.line_side != "new",
                    item.line,
                    item.category,
                    item.rule_id,
                ),
            )
        )
