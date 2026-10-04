# Copyright 2026 Anthropic PBC
# SPDX-License-Identifier: Apache-2.0

"""本 fork 的本地 Messages 示例接入；核心业务配置与托管平台配置各自保留。"""

from __future__ import annotations

import os
from typing import TypeVar

from commerce_common.config import BaseAgentConfig

ConfigT = TypeVar("ConfigT", bound=BaseAgentConfig)


def _provider() -> str:
    value = os.environ.get("COMMERCE_MODEL_PROVIDER", "anthropic").strip().lower()
    if value not in {"anthropic", "deepseek"}:
        raise ValueError("COMMERCE_MODEL_PROVIDER 只能是 anthropic 或 deepseek")
    return value


def configure_demo_provider() -> None:
    """在创建 AsyncAnthropic 前选定官方地址；SDK 鉴权链不能用于 DeepSeek。"""
    if _provider() != "deepseek":
        return
    if os.environ.get("COMMERCE_DEMO_AUTH", "").lower() == "sdk":
        raise ValueError("DeepSeek 直连不能使用 COMMERCE_DEMO_AUTH=sdk")
    key = os.environ.get("DEEPSEEK_API_KEY", "").strip()
    if not key or key.startswith("replace-"):
        raise ValueError("DeepSeek 直连需要 DEEPSEEK_API_KEY")
    os.environ["ANTHROPIC_BASE_URL"] = "https://api.deepseek.com/anthropic"
    os.environ["ANTHROPIC_API_KEY"] = key
    os.environ.pop("ANTHROPIC_AUTH_TOKEN", None)


def configure_demo_model(config: ConfigT) -> ConfigT:
    """主 Loop、记忆提取和分析委派统一模型；关闭本接入未验收的平台工具。"""
    if _provider() != "deepseek":
        return config
    model = os.environ.get("DEEPSEEK_MODEL", "").strip() or "deepseek-flash"
    updates = {
        "model": model,
        "memory_model": model,
        "thinking_effort": None,
        "enable_web_search": False,
    }
    if hasattr(config, "analysis_use_code_execution"):
        updates.update(analysis_model=model, analysis_use_code_execution=False)
    return type(config).model_validate(config.model_dump() | updates)
