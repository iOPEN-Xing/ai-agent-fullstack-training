# Copyright 2026 Anthropic PBC
# SPDX-License-Identifier: Apache-2.0

import importlib
import os
from unittest.mock import patch

import pytest

from merchant_agent import MerchantAgentConfig
from shopping_agent import ShoppingAgentConfig


@pytest.fixture(autouse=True)
def provider_env():
    # load_dotenv 和接入函数会直接修改 os.environ；整份快照避免测试间泄漏。
    with patch.dict(os.environ):
        for name in (
            "COMMERCE_MODEL_PROVIDER",
            "COMMERCE_DEMO_AUTH",
            "DEEPSEEK_API_KEY",
            "DEEPSEEK_MODEL",
            "ANTHROPIC_API_KEY",
            "ANTHROPIC_AUTH_TOKEN",
            "ANTHROPIC_BASE_URL",
        ):
            os.environ.pop(name, None)
        yield


def test_direct_credentials_replace_anthropic_credentials(monkeypatch):
    from demo_common.deepseek import configure_demo_provider

    monkeypatch.setenv("COMMERCE_MODEL_PROVIDER", "deepseek")
    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-deepseek-key")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "old-key")
    monkeypatch.setenv("ANTHROPIC_AUTH_TOKEN", "old-token")
    configure_demo_provider()
    assert os.environ["ANTHROPIC_BASE_URL"] == "https://api.deepseek.com/anthropic"
    assert os.environ["ANTHROPIC_API_KEY"] == "test-deepseek-key"
    assert "ANTHROPIC_AUTH_TOKEN" not in os.environ


@pytest.mark.parametrize("vertical", ["retail", "travel", "telecom", "entertainment"])
def test_vertical_factories_select_flash_for_all_model_calls(monkeypatch, vertical):
    monkeypatch.setenv("COMMERCE_MODEL_PROVIDER", "deepseek")
    module = importlib.import_module(f"{vertical}.api.agent_config")
    shopping, merchant = module.build_shopping_config(), module.build_merchant_config("Store")
    for config in (shopping, merchant):
        assert config.model == config.memory_model == "deepseek-flash"
        assert config.thinking_request_fields() == {"thinking": {"type": "disabled"}}
        assert not config.enable_web_search
    assert merchant.analysis_model == "deepseek-flash"
    assert not merchant.analysis_use_code_execution
    assert merchant.require_host_approval
    assert merchant.brand_name == "Store"


def test_missing_deepseek_key_does_not_fall_back(monkeypatch):
    from demo_common.deepseek import configure_demo_provider

    monkeypatch.setenv("COMMERCE_MODEL_PROVIDER", "deepseek")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "different-provider-key")
    with pytest.raises(ValueError, match="DEEPSEEK_API_KEY"):
        configure_demo_provider()


def test_sdk_auth_is_rejected_for_the_direct_profile(monkeypatch):
    from demo_common.deepseek import configure_demo_provider

    monkeypatch.setenv("COMMERCE_MODEL_PROVIDER", "deepseek")
    monkeypatch.setenv("COMMERCE_DEMO_AUTH", "sdk")
    with pytest.raises(ValueError, match="COMMERCE_DEMO_AUTH"):
        configure_demo_provider()


def test_original_profile_preserves_role_defaults():
    from demo_common.deepseek import configure_demo_model

    for config in (ShoppingAgentConfig(), MerchantAgentConfig()):
        assert configure_demo_model(config) is config


def test_unknown_profile_fails_before_a_request(monkeypatch):
    from demo_common.deepseek import configure_demo_provider

    monkeypatch.setenv("COMMERCE_MODEL_PROVIDER", "typo")
    with pytest.raises(ValueError, match="COMMERCE_MODEL_PROVIDER"):
        configure_demo_provider()


def test_sdk_loader_rejects_trimmed_direct_profile_before_clearing_keys(monkeypatch, tmp_path):
    from demo_common.host import load_demo_env

    monkeypatch.setenv("COMMERCE_MODEL_PROVIDER", " deepseek ")
    monkeypatch.setenv("COMMERCE_DEMO_AUTH", "sdk")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "unchanged-on-rejection")
    with pytest.raises(ValueError, match="COMMERCE_DEMO_AUTH"):
        load_demo_env(tmp_path)
    assert os.environ["ANTHROPIC_API_KEY"] == "unchanged-on-rejection"


def test_environment_loader_configures_direct_profile_before_client_creation(monkeypatch, tmp_path):
    from demo_common import host

    monkeypatch.setattr(host, "REPO_ROOT", tmp_path)
    (tmp_path / ".env").write_text(
        "COMMERCE_MODEL_PROVIDER=deepseek\nDEEPSEEK_API_KEY=test-file-key\n"
    )
    host.load_demo_env(tmp_path / "example")
    assert os.environ["ANTHROPIC_BASE_URL"] == "https://api.deepseek.com/anthropic"
    assert os.environ["ANTHROPIC_API_KEY"] == "test-file-key"


async def test_direct_authentication_error_names_the_correct_key(monkeypatch):
    from types import SimpleNamespace

    import anthropic
    import httpx

    from demo_common.host import stream_turn

    class UnauthorizedAgent:
        async def stream_turn(self, messages, session, state):
            response = httpx.Response(
                401, request=httpx.Request("POST", "https://api.deepseek.com/anthropic/v1/messages")
            )
            raise anthropic.AuthenticationError("invalid credentials", response=response, body=None)
            yield  # 此接口是 async iterator。

    monkeypatch.setenv("COMMERCE_MODEL_PROVIDER", "deepseek")
    response = stream_turn(
        UnauthorizedAgent(),
        None,
        SimpleNamespace(messages=[], state=None),
        None,
        env_hint="example/.env",
    )
    payload = "".join([chunk async for chunk in response.body_iterator])
    assert "DeepSeek" in payload and "DEEPSEEK_API_KEY" in payload
    assert "ANTHROPIC_API_KEY" not in payload and "COMMERCE_DEMO_AUTH=sdk" not in payload
