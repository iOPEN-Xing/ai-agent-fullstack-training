import asyncio
import json
import sys
from pathlib import Path
from typing import Any

from mcp import Client, StdioServerParameters
from mcp.client.stdio import stdio_client


base_dir = Path(__file__).parent


def result_payload(result: Any, max_chars: int = 2_000) -> dict[str, Any]:
    """统一远端业务结果；成功和错误都受序列化后的字符预算约束。"""
    if max_chars < 128:
        raise ValueError("max_chars 至少为 128，需容纳标准错误结果")
    texts = []
    for block in result.content:
        text = getattr(block, "text", None)
        if isinstance(text, str):
            texts.append(text)
    text = "\n".join(texts)
    if result.is_error:
        payload = {"ok": False, "code": "MCP_TOOL_ERROR", "message": text or "远端工具执行失败"}
    elif result.structured_content is not None:
        value = result.structured_content
        if not isinstance(value, dict) or ("ok" in value and not isinstance(value["ok"], bool)):
            return {"ok": False, "code": "MCP_RESULT_INVALID"}
        payload = {"ok": True, **value}
    else:
        payload = {"ok": True, "text": text}

    try:
        serialized = json.dumps(payload, ensure_ascii=False, allow_nan=False)
    except (TypeError, ValueError):
        return {"ok": False, "code": "MCP_RESULT_INVALID"}
    if len(serialized) > max_chars:
        return {"ok": False, "code": "RESULT_TOO_LARGE"}
    return payload


async def main() -> None:
    """以 stdio 启动本地 Server，发现工具并演示一次订单查询。"""
    parameters = StdioServerParameters(
        command=sys.executable,
        args=[str(base_dir / "mcp_server_v1.py")],
        cwd=base_dir,
    )

    async with Client(stdio_client(parameters)) as client:
        tools = await client.list_tools()
        print("可用工具:", [tool.name for tool in tools.tools])

        result = await client.call_tool("get_order", {"order_id": "ord_1001"})
        print(result_payload(result))


if __name__ == "__main__":
    asyncio.run(main())
