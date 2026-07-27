#
# Tencent is pleased to support the open source community by making trpc-agent-python available.
#
# Copyright (C) 2026 Tencent. All rights reserved.
#
# trpc-agent-python is licensed under the Apache License Version 2.0.
#

"""End-to-end checks for the user-facing release documentation contract."""

from __future__ import annotations

from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]


def test_release_docs_cover_usage_safety_design_risks_and_acceptance() -> None:
    """验证 README 与设计说明覆盖 E2 约定的可执行使用、安全和验收信息。"""

    readme = (PROJECT_ROOT / "README.md").read_text(encoding="utf-8")
    design = (PROJECT_ROOT / "DESIGN.md").read_text(encoding="utf-8")
    design_statement = design.split("## 风险表", maxsplit=1)[0]
    chinese_character_count = sum("\u4e00" <= character <= "\u9fff" for character in design_statement)

    required_readme_terms = (
        "--diff-file",
        "--repo-path",
        "--files",
        "--fixture",
        "--dry-run",
        "--model-mode real",
        "TRPC_AGENT_API_KEY",
        "TRPC_AGENT_BASE_URL",
        "TRPC_AGENT_MODEL_NAME",
        "skills/code-review/scripts/manifest.json",
        "--sandbox local",
        "1 MiB",
        "2 MiB",
        "公开代理",
        "不证明",
    )
    required_design_topics = (
        "Skill",
        "沙箱",
        "Filter",
        "监控",
        "数据库",
        "去重",
        "脱敏",
        "安全边界",
    )

    assert all(term in readme for term in required_readme_terms)
    assert all(term in design for term in required_design_topics)
    assert 300 <= chinese_character_count <= 500
    assert design.count("|") >= 24
    assert all(f"AC{number}" in readme for number in range(1, 9))
