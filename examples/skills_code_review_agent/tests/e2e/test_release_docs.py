#
# Tencent is pleased to support the open source community by making trpc-agent-python available.
#
# Copyright (C) 2026 Tencent. All rights reserved.
#
# trpc-agent-python is licensed under the Apache License Version 2.0.
#

"""End-to-end checks for the user-facing release documentation contract."""

from __future__ import annotations

import re
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
MARKDOWN_LINK_PATTERN = re.compile(r"\[[^\]]+\]\(([^)]+)\)")


def _local_markdown_targets(document_path: Path) -> list[Path]:
    """提取 Markdown 中的本地链接并解析为可验证的绝对路径。"""

    document = document_path.read_text(encoding="utf-8")
    targets: list[Path] = []
    for raw_target in MARKDOWN_LINK_PATTERN.findall(document):
        target = raw_target.strip("<>").split("#", maxsplit=1)[0]
        if not target or target.startswith(("http://", "https://", "mailto:")):
            continue
        targets.append((document_path.parent / target).resolve())
    return targets


def test_release_docs_cover_usage_safety_design_risks_and_acceptance() -> None:
    """验证 README 与设计说明覆盖 E2 约定的可执行使用、安全和验收信息。"""

    readme = (PROJECT_ROOT / "README.md").read_text(encoding="utf-8")
    design = (PROJECT_ROOT / "DESIGN.md").read_text(encoding="utf-8")
    design_statement = design.split("## 方案设计说明", maxsplit=1)[1].split(
        "## 规格与交付范围",
        maxsplit=1,
    )[0]
    chinese_character_count = sum("\u4e00" <= character <= "\u9fff" for character in design_statement)

    required_readme_terms = (
        "## 规格依据",
        "DEV_SPEC.md",
        "## 交付物总览",
        "OPERATIONS.md",
        ".env.example",
        ".venv/bin/python",
        "skills/code-review/SKILL.md",
        "codereview/store/models.py",
        "tests/fixtures/diffs/",
        "sample_output/review_report.json",
        "--diff-file",
        "--repo-path",
        "--files",
        "--fixture",
        "--dry-run",
        "--model-mode real",
        "user-query",
        "--log-level INFO",
        "report_files",
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
        "## 规格与交付范围",
        "DEV_SPEC.md",
        "## 交付物与架构映射",
        "OPERATIONS.md",
        "user-query",
        "--log-level INFO",
        "Bash",
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
    assert "官方隐藏样本待官方验收" in readme
    assert "官方隐藏样本待官方验收" in design
    assert 300 <= chinese_character_count <= 500
    assert design.count("|") >= 24
    assert all(f"AC{number}" in readme for number in range(1, 9))
    assert all(f"AC{number}" in design for number in range(1, 9))


def test_release_docs_local_links_resolve() -> None:
    """验证 README 与设计说明中的本地交付物链接都指向真实文件或目录。"""

    document_paths = (PROJECT_ROOT / "README.md", PROJECT_ROOT / "DESIGN.md")
    local_targets = [
        target
        for document_path in document_paths
        for target in _local_markdown_targets(document_path)
    ]

    assert local_targets
    assert all(target.exists() for target in local_targets)
