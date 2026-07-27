#
# Tencent is pleased to support the open source community by making trpc-agent-python available.
#
# Copyright (C) 2026 Tencent. All rights reserved.
#
# trpc-agent-python is licensed under the Apache License Version 2.0.
#

"""Integration tests for the SDK-backed code-review Agent entry."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from agent.agent import create_review_agent  # noqa: E402


class _Pipeline:
    """记录输入的最小 pipeline 替身，避免本测试复制实际检测规则。"""

    def __init__(self) -> None:
        """初始化调用记录。"""

        self.calls: list[dict[str, Any]] = []

    def run(self, **options: Any) -> dict[str, Any]:
        """返回固定 canonical finding 集合，验证 Agent 只委托唯一 pipeline。"""

        self.calls.append(options)
        return {"findings": [{"file": "src/a.py", "line": 1, "category": "security"}]}


def test_agent_loads_code_review_skill_and_delegates_to_shared_pipeline() -> None:
    """验证 Agent 组装 SDK SkillRepository/SkillToolSet，且不再实现第二条检测链路。"""

    pipeline = _Pipeline()
    agent = create_review_agent(pipeline=pipeline, skill_root=PROJECT_ROOT / "skills")

    result = agent.review(fixture="01_clean")

    assert result["findings"] == [{"file": "src/a.py", "line": 1, "category": "security"}]
    assert pipeline.calls == [{"fixture": "01_clean"}]
    assert agent.llm_agent.name == "code_review_agent"
    assert agent.skill_toolset.repository is agent.skill_repository
    assert agent.skill_repository.skill_list() == ["code-review"]
    assert agent.agent_run_count == 1
