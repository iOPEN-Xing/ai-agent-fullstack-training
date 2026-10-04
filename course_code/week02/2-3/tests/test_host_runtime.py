import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from mcp_host_v1 import ToolCall, ToolDefinition, ToolRuntime, discover_tools

SCHEMA = {
    "type": "object",
    "properties": {"order_id": {"type": "string"}},
    "required": ["order_id"],
    "additionalProperties": False,
}


def definition(handler):
    return {"orders_get_order": ToolDefinition("orders_get_order", "查询订单", SCHEMA, handler)}


@pytest.mark.parametrize("arguments", [None, [], {}, {"order_id": 1}])
async def test_invalid_arguments_never_reach_the_remote_handler(arguments):
    handler = AsyncMock()
    runtime = ToolRuntime()
    result = await runtime.execute(ToolCall("call-1", "orders_get_order", arguments), definition(handler))
    assert result["code"] == "INVALID_ARGUMENT"
    handler.assert_not_awaited()
    assert [event["event"] for event in runtime.trace] == ["runtime_rejected"]


async def test_runtime_keeps_the_host_call_id_when_remote_payload_forges_it():
    handler = AsyncMock(return_value={"ok": True, "tool_call_id": "forged"})
    result = await ToolRuntime().execute(
        ToolCall("host-id", "orders_get_order", {"order_id": "ord_1001"}), definition(handler)
    )
    assert result["tool_call_id"] == "host-id"


async def test_timeout_is_unknown_outcome_and_is_not_retried():
    handler = AsyncMock(side_effect=lambda *_: None)

    async def wait(*_):
        await asyncio.sleep(1)

    handler.side_effect = wait
    runtime = ToolRuntime(timeout_seconds=0.01)
    result = await runtime.execute(
        ToolCall("slow", "orders_get_order", {"order_id": "x"}), definition(handler)
    )
    assert result == {"ok": False, "code": "TOOL_RESULT_UNKNOWN", "tool_call_id": "slow"}
    assert handler.await_count == 1
    assert [event["event"] for event in runtime.trace] == ["server_call", "tool_result"]


async def test_transport_error_has_no_raw_exception_or_automatic_retry():
    handler = AsyncMock(side_effect=RuntimeError("private transport diagnostic"))
    result = await ToolRuntime().execute(
        ToolCall("broken", "orders_get_order", {"order_id": "x"}), definition(handler)
    )
    assert result["code"] == "TOOL_RESULT_UNKNOWN"
    assert "private" not in str(result)
    assert handler.await_count == 1


async def test_cancellation_propagates_instead_of_becoming_a_business_error():
    handler = AsyncMock(side_effect=asyncio.CancelledError())
    with pytest.raises(asyncio.CancelledError):
        await ToolRuntime().execute(
            ToolCall("cancel", "orders_get_order", {"order_id": "x"}), definition(handler)
        )


async def test_discovery_only_exposes_the_host_allowlist_and_binds_remote_names():
    client = SimpleNamespace(
        list_tools=AsyncMock(
            return_value=SimpleNamespace(
                tools=[
                    SimpleNamespace(name=name, description="", input_schema=SCHEMA)
                    for name in ["get_order", "create_ticket"]
                ]
            )
        ),
        call_tool=AsyncMock(
            return_value=SimpleNamespace(is_error=False, content=[], structured_content={"ok": True})
        ),
    )
    tools = await discover_tools(client, "orders", allowed_names={"get_order"})
    assert list(tools) == ["orders_get_order"]
    result = await ToolRuntime().execute(ToolCall("read", "orders_get_order", {"order_id": "x"}), tools)
    assert result["tool_call_id"] == "read"
    client.call_tool.assert_awaited_once_with("get_order", {"order_id": "x"})
    rejected = await ToolRuntime().execute(ToolCall("write", "orders_create_ticket", {}), tools)
    assert rejected["code"] == "TOOL_NOT_FOUND" and client.call_tool.await_count == 1
