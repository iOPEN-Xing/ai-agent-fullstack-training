import json
from types import SimpleNamespace
from unittest.mock import AsyncMock

import httpx
import pytest
from mcp_host_v1 import DeepSeekProvider, ToolCall, ToolDefinition, ToolRuntime, run_agent
from openai import AsyncOpenAI
from loop_v1 import create_provider


@pytest.mark.parametrize("arguments", ['{"order_id":"a"}', "not-json"])
@pytest.mark.parametrize("entry", ["host", "basic"])
async def test_provider_retains_all_calls_and_native_fields_and_disables_thinking(
    monkeypatch, arguments, entry
):
    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-deepseek-key")
    monkeypatch.setenv("DEEPSEEK_MODEL", "deepseek-flash")
    monkeypatch.setenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com/v1")
    calls = [
        {"id": name, "type": "function", "function": {"name": "orders_get_order", "arguments": arguments}}
        for name in ["call-1", "call-2"]
    ]

    async def respond(request):
        body = json.loads(request.content)
        assert request.url == "https://api.deepseek.com/v1/chat/completions"
        assert body["thinking"] == {"type": "disabled"} and body["max_tokens"] == 1024
        return httpx.Response(
            200,
            json={
                "id": "reply",
                "object": "chat.completion",
                "created": 0,
                "model": "deepseek-flash",
                "choices": [
                    {
                        "index": 0,
                        "finish_reason": "tool_calls",
                        "message": {
                            "role": "assistant",
                            "content": None,
                            "reasoning_content": "retained-field",
                            "tool_calls": calls,
                        },
                    }
                ],
            },
        )

    http_client = httpx.AsyncClient(transport=httpx.MockTransport(respond))
    monkeypatch.setattr(
        f"{'mcp_host_v1' if entry == 'host' else 'loop_v1'}.AsyncOpenAI",
        lambda **kwargs: AsyncOpenAI(**kwargs, http_client=http_client),
    )
    provider = DeepSeekProvider() if entry == "host" else create_provider()
    try:
        reply = await provider.complete([{"role": "user", "content": "查订单"}], [])
        assert [call.id for call in reply.tool_calls] == ["call-1", "call-2"]
        assert reply.message["reasoning_content"] == "retained-field"
        assert reply.message["tool_calls"][0]["function"]["arguments"] == arguments
        if arguments == "not-json" and entry == "host":
            assert all(call.arguments is None for call in reply.tool_calls)
    finally:
        await provider.client.close()


async def test_loop_returns_every_call_result_in_order_without_rebuilding_the_assistant():
    calls = (
        ToolCall("one", "orders_get_order", {"order_id": "a"}),
        ToolCall("two", "orders_get_order", {"order_id": "b"}),
    )
    assistant = {
        "role": "assistant",
        "reasoning_content": "keep-original",
        "tool_calls": [
            {
                "id": call.id,
                "type": "function",
                "function": {"name": call.name, "arguments": json.dumps(call.arguments)},
            }
            for call in calls
        ],
    }
    contexts = []

    async def complete(messages, _tools):
        contexts.append(json.loads(json.dumps(messages)))
        if len(contexts) == 1:
            return SimpleNamespace(text=None, tool_calls=calls, message=assistant, tool_call=None)
        return SimpleNamespace(text="done", tool_calls=(), message={"role": "assistant", "content": "done"})

    handler = AsyncMock(return_value={"ok": True})
    tools = {"orders_get_order": ToolDefinition("orders_get_order", "查询", {"type": "object"}, handler)}
    assert await run_agent(SimpleNamespace(complete=complete), ToolRuntime(), tools, "query") == "done"
    assert contexts[1][1] == assistant
    assert [message["tool_call_id"] for message in contexts[1] if message["role"] == "tool"] == ["one", "two"]
    assert handler.await_count == 2


async def test_round_limit_is_failure_instead_of_an_empty_success():
    provider = SimpleNamespace(
        complete=AsyncMock(
            return_value=SimpleNamespace(
                text=None, tool_calls=(), message={"role": "assistant"}, tool_call=None
            )
        )
    )
    with pytest.raises(RuntimeError, match="MODEL_REPLY_INVALID"):
        await run_agent(provider, ToolRuntime(), {}, "query", max_rounds=1)


async def test_a_large_batch_is_rejected_before_any_tool_side_effect():
    calls = tuple(ToolCall(str(i), "orders_get_order", {}) for i in range(9))
    provider = SimpleNamespace(
        complete=AsyncMock(
            return_value=SimpleNamespace(text=None, tool_calls=calls, message={"role": "assistant"})
        )
    )
    handler = AsyncMock(return_value={"ok": True})
    tools = {"orders_get_order": ToolDefinition("orders_get_order", "查询", {"type": "object"}, handler)}
    with pytest.raises(RuntimeError, match="MAX_TOOL_CALLS_EXCEEDED"):
        await run_agent(provider, ToolRuntime(), tools, "query")
    handler.assert_not_awaited()
