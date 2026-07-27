#
# Tencent is pleased to support the open source community by making trpc-agent-python available.
#
# Copyright (C) 2026 Tencent. All rights reserved.
#
# trpc-agent-python is licensed under the Apache License Version 2.0.
#

"""Prompts used by the optional report-enhancement layer."""

ENHANCEMENT_INSTRUCTION = """只增强已脱敏代码评审报告的修复建议、摘要和人工复核提示。
不得新增、删除、合并或重新分级 finding；不得请求原始 diff、代码、环境变量或凭据。"""

__all__ = ["ENHANCEMENT_INSTRUCTION"]
