import os
import subprocess
import sys

from mcp import Client, StdioServerParameters
from mcp.client.stdio import stdio_client
from mcp_client_v1 import base_dir
from mcp_host_v1 import ToolCall, ToolRuntime, discover_tools


async def test_real_stdio_discovery_validation_remote_error_resource_and_prompt():
    parameters = StdioServerParameters(
        command=sys.executable, args=[str(base_dir / "mcp_server_v1.py")], cwd=base_dir
    )
    async with Client(stdio_client(parameters)) as client:
        tools = await discover_tools(client, "orders", allowed_names={"get_order"})
        runtime = ToolRuntime()
        ok = await runtime.execute(ToolCall("ok", "orders_get_order", {"order_id": "ord_1001"}), tools)
        assert ok["status"] == "pending" and ok["amount_cents"] == 2999
        assert (await runtime.execute(ToolCall("bad", "orders_get_order", {}), tools))[
            "code"
        ] == "INVALID_ARGUMENT"
        missing = await runtime.execute(
            ToolCall("missing", "orders_get_order", {"order_id": "missing"}), tools
        )
        assert missing["code"] == "MCP_TOOL_ERROR"
        assert sum(event["event"] == "server_call" for event in runtime.trace) == 2
        resource = await client.read_resource("policy://order-status")
        assert "pending=待处理" in resource.contents[0].text
        prompt = await client.get_prompt("order_assistant", {"order_id": "ord_1001"})
        assert "ord_1001" in prompt.messages[0].content.text


def test_missing_credentials_fail_the_basic_cli_with_a_nonzero_exit():
    env = os.environ.copy()
    env.pop("DEEPSEEK_API_KEY", None)
    result = subprocess.run(
        [sys.executable, str(base_dir / "loop_v1.py")], env=env, capture_output=True, text=True, timeout=15
    )
    assert result.returncode != 0
    assert "DEEPSEEK_API_KEY" in result.stderr
