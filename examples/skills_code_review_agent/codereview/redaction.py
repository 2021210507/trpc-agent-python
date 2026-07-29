#
# Tencent is pleased to support the open source community by making trpc-agent-python available.
#
# Copyright (C) 2026 Tencent. All rights reserved.
#
# trpc-agent-python is licensed under the Apache License Version 2.0.
#

"""Host-side access to the Skill-owned sensitive-data redactor."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Mapping


_PROJECT_ROOT = Path(__file__).resolve().parents[1]
_SCRIPTS_ROOT = _PROJECT_ROOT / "skills" / "code-review" / "scripts"
if str(_SCRIPTS_ROOT) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_ROOT))

from lib import secret_rules as _SECRET_RULES  # noqa: E402


def redact_text(text: str) -> str:
    """使用已加载 Skill 的规则表脱敏单个输出字符串。"""

    return _SECRET_RULES.redact_text(text)


def contains_plaintext_secret(value: Any) -> bool:
    """递归检查输出值是否仍含未脱敏的敏感信息语法。"""

    if isinstance(value, str):
        return _SECRET_RULES.contains_secret(value)
    if isinstance(value, Mapping):
        return any(
            contains_plaintext_secret(key) or contains_plaintext_secret(item)
            for key, item in value.items()
        )
    if isinstance(value, (list, tuple, set, frozenset)):
        return any(contains_plaintext_secret(item) for item in value)
    return False


def redact_data(value: Any) -> Any:
    """在对象离开宿主前递归脱敏其中的所有字符串。"""

    if isinstance(value, str):
        return redact_text(value)
    if isinstance(value, Mapping):
        return {redact_data(key): redact_data(item) for key, item in value.items()}
    if isinstance(value, list):
        return [redact_data(item) for item in value]
    if isinstance(value, tuple):
        return tuple(redact_data(item) for item in value)
    if isinstance(value, set):
        return {redact_data(item) for item in value}
    if isinstance(value, frozenset):
        return frozenset(redact_data(item) for item in value)
    return value


def redact_transport_fields(**fields: Any) -> dict[str, Any]:
    """为报告、Filter、异常和沙箱字段应用统一脱敏路径。"""

    return {name: redact_data(value) for name, value in fields.items()}
