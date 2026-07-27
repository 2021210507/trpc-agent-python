#
# Tencent is pleased to support the open source community by making trpc-agent-python available.
#
# Copyright (C) 2026 Tencent. All rights reserved.
#
# trpc-agent-python is licensed under the Apache License Version 2.0.
#

"""LlmAgent and SkillToolSet assembly for code review."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncGenerator
import json
from pathlib import Path
from typing import Any, Protocol

from trpc_agent_sdk.agents import LlmAgent
from trpc_agent_sdk.models import LLMModel, LlmResponse
from trpc_agent_sdk.runners import Runner
from trpc_agent_sdk.sessions import InMemorySessionService
from trpc_agent_sdk.skills import SkillToolSet, create_default_skill_repository
from trpc_agent_sdk.types import Content, Part


class PipelinePort(Protocol):
    """定义 Agent 唯一允许调用的评审 pipeline 接口，禁止复制检测逻辑。"""

    def run(self, **input_options: Any) -> Any:
        """执行已组装的唯一 ReviewPipeline 链路。"""


class _AgentAssemblyModel(LLMModel):
    """为无 Key 的 Agent 组装提供无网络模型，真实评审仍只由 pipeline 驱动。"""

    @classmethod
    def supported_models(cls) -> list[str]:
        """声明内部固定模型名，避免注册或读取外部模型配置。"""

        return [r"code-review-agent-assembly"]

    async def _generate_async_impl(
        self,
        _request: Any,
        stream: bool = False,
        ctx: Any = None,
    ) -> AsyncGenerator[LlmResponse, None]:
        """返回固定安全文本；该模型不执行规则、不访问网络也不解析评审输入。"""

        del stream, ctx
        yield LlmResponse(content=Content(parts=[Part.from_text(text="请使用受控 code-review 工作流。")]))

    def validate_request(self, request: Any) -> None:
        """复用 SDK 基础输入验证，使组装模型的失败语义与普通模型一致。"""

        super().validate_request(request)


class CodeReviewAgent:
    """将 SDK Agent/Skill 能力与唯一 ReviewPipeline 组合的公开入口。"""

    def __init__(
        self,
        *,
        pipeline: PipelinePort,
        skill_root: Path,
        model: LLMModel | None = None,
    ) -> None:
        """加载受控 SkillRepository，并保留 pipeline 作为唯一检测与持久化实现。"""

        self._pipeline = pipeline
        self.skill_repository = create_default_skill_repository(str(skill_root))
        self.skill_toolset = SkillToolSet(repository=self.skill_repository)
        self.llm_agent = LlmAgent(
            name="code_review_agent",
            model=model or _AgentAssemblyModel("code-review-agent-assembly"),
            tools=[self.skill_toolset],
            instruction=(
                "使用 code-review Skill 的受控工作流；不得直接执行任意命令，"
                "检测必须由 ReviewPipeline 完成。"
            ),
        )
        self.agent_run_count = 0

    def review(self, **input_options: Any) -> Any:
        """先运行 SDK Agent/Skill 工具链，再把结构化输入交给共享 ReviewPipeline。"""

        asyncio.run(self._run_sdk_agent(input_options))
        return self._pipeline.run(**input_options)

    async def _run_sdk_agent(self, input_options: dict[str, Any]) -> None:
        """执行无原始代码的 Agent 回合，使 SkillToolSet 在标准 SDK Runner 中参与请求组装。"""

        safe_input_kinds = sorted(name for name, value in input_options.items() if value is not None)
        prompt = json.dumps(
            {"operation": "controlled_code_review", "input_kinds": safe_input_kinds},
            ensure_ascii=False,
            sort_keys=True,
        )
        service = InMemorySessionService()
        runner = Runner(
            app_name="code_review_agent",
            agent=self.llm_agent,
            session_service=service,
            enable_post_turn_processing=False,
        )
        try:
            message = Content(parts=[Part.from_text(text=prompt)])
            async for _event in runner.run_async(
                user_id="code_review",
                session_id="review_request",
                new_message=message,
            ):
                pass
            self.agent_run_count += 1
        finally:
            await runner.close()


def create_review_agent(
    *,
    pipeline: PipelinePort,
    skill_root: Path,
    model: LLMModel | None = None,
) -> CodeReviewAgent:
    """构造一个经 SDK SkillRepository 与 SkillToolSet 绑定的代码评审 Agent。"""

    return CodeReviewAgent(pipeline=pipeline, skill_root=skill_root, model=model)


__all__ = ["CodeReviewAgent", "create_review_agent"]
