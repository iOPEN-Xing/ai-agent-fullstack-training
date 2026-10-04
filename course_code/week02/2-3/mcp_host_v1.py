from __future__ import annotations

import asyncio
import argparse
import json
import math
import os
import sys
from dataclasses import dataclass
from collections.abc import Awaitable, Callable
from typing import Any, Protocol

from jsonschema import ValidationError, validate
from jsonschema.validators import validator_for
from mcp import Client, StdioServerParameters
from mcp.client.stdio import stdio_client
from openai import AsyncOpenAI

from mcp_client_v1 import base_dir, result_payload


@dataclass(frozen=True)
class ToolCall:
    """Host 交给 Runtime 的工具提议；参数仍需校验。"""

    id: str
    name: str
    arguments: Any  # 参数是模型输出，Runtime 校验前不能假定已经是对象。


@dataclass(frozen=True)
class ModelReply:
    """保留完整 assistant 消息；同轮工具调用按原顺序逐一回传。"""

    text: str | None = None
    tool_calls: tuple[ToolCall, ...] = ()
    message: dict[str, Any] | None = None


class LLMProvider(Protocol):
    """定义 Agent Loop 所需的模型调用抽象。"""

    async def complete(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
    ) -> ModelReply: ...


class DeepSeekProvider:
    """通过 OpenAI-compatible API 调用 DeepSeek，并规范化模型回复。"""

    def __init__(self) -> None:
        """读取模型配置并创建禁用 SDK 自动重试的异步客户端。"""
        api_key = os.getenv("DEEPSEEK_API_KEY", "").strip()
        if not api_key or api_key.startswith("replace-"):
            raise RuntimeError("请先设置环境变量 DEEPSEEK_API_KEY")
        base_url = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com/v1").strip().rstrip("/")
        if base_url not in {"https://api.deepseek.com", "https://api.deepseek.com/v1"}:
            raise RuntimeError("DEEPSEEK_BASE_URL 必须使用官方地址")
        self.model = os.getenv("DEEPSEEK_MODEL", "").strip() or "deepseek-flash"
        self.client = AsyncOpenAI(
            api_key=api_key,
            base_url=base_url,
            max_retries=0,
            timeout=30,
        )

    async def complete(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
    ) -> ModelReply:
        """关闭思考并限制输出；原生字段和全部 Tool Call 都进入回复。"""
        response = await self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            tools=tools,
            tool_choice="auto",
            max_tokens=1024,
            extra_body={"thinking": {"type": "disabled"}},
        )
        message = response.choices[0].message
        calls = []
        for call in message.tool_calls or []:
            try:
                arguments = json.loads(call.function.arguments or "null")
            except json.JSONDecodeError:
                arguments = None  # 非法参数交给 Runtime 拒绝，不能变成可执行的空对象。
            calls.append(ToolCall(call.id, call.function.name, arguments))
        return ModelReply(
            text=None if calls else message.content,
            tool_calls=tuple(calls),
            message=message.model_dump(exclude_none=True),
        )


ToolHandler = Callable[[str, dict[str, Any]], Awaitable[dict[str, Any]]]


@dataclass(frozen=True)
class ToolDefinition:
    """Host 侧工具定义，包含模型可见 Schema 与远端调用处理器。"""

    name: str
    description: str
    input_schema: dict[str, Any]
    handler: ToolHandler

    def to_model_tool(self) -> dict[str, Any]:
        """转换为 OpenAI-compatible 的 function tool 描述。"""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.input_schema,
            },
        }


class ToolRuntime:
    """在调用 MCP Server 前执行工具查找、参数校验与执行轨迹记录。"""

    def __init__(self, timeout_seconds: float = 10) -> None:
        """初始化空的执行轨迹，供副作用和调用顺序断言使用。"""
        if not math.isfinite(timeout_seconds) or timeout_seconds <= 0:
            raise ValueError("timeout_seconds 必须为有限正数")
        self.timeout_seconds = timeout_seconds
        self.trace: list[dict[str, Any]] = []

    async def execute(
        self,
        call: ToolCall,
        tools: dict[str, ToolDefinition],
    ) -> dict[str, Any]:
        """校验工具和参数；仅校验通过后才调用对应远端处理器。"""
        tool = tools.get(call.name)
        if not tool:
            return self._reject(call, "TOOL_NOT_FOUND")
        if not isinstance(call.arguments, dict):
            return self._reject(call, "INVALID_ARGUMENT", "工具参数必须是 JSON 对象")
        try:
            validate(instance=call.arguments, schema=tool.input_schema)
        except ValidationError as exc:
            return self._reject(call, "INVALID_ARGUMENT", exc.message)

        self.trace.append(
            {
                "event": "server_call",
                "tool_call_id": call.id,
                "name": call.name,
                "arguments": call.arguments,
            }
        )
        try:
            async with asyncio.timeout(self.timeout_seconds):
                result = await tool.handler(call.id, call.arguments)
        except Exception:
            # 已进入远端调用，超时或断连都不能证明副作用没有发生。
            # 不自动重试，也不把可能含凭证的传输异常直接放进模型上下文。
            result = {"ok": False, "code": "TOOL_RESULT_UNKNOWN"}
        # 关联 ID 固定为原调用 ID，远端业务字段无权覆盖。
        result = {**result, "tool_call_id": call.id}
        self.trace.append(
            {
                "event": "tool_result",
                "tool_call_id": call.id,
                "name": call.name,
                "payload": result,
            }
        )
        return result

    def _reject(
        self,
        call: ToolCall,
        code: str,
        message: str | None = None,
    ) -> dict[str, Any]:
        """记录本地拒绝，并返回未触发 Server 调用的结构化错误。"""
        payload = {"ok": False, "code": code, "tool_call_id": call.id}
        if message:
            payload["message"] = message
        self.trace.append(
            {
                "event": "runtime_rejected",
                "tool_call_id": call.id,
                "name": call.name,
                "payload": payload,
            }
        )
        return payload


async def discover_tools(
    client: Client,
    server_id: str,
    *,
    allowed_names: set[str],
) -> dict[str, ToolDefinition]:
    """只投影 Host 允许的工具；发现能力不会自动授予执行权限。"""
    result = await client.list_tools()
    definitions: dict[str, ToolDefinition] = {}
    for remote in result.tools:
        if remote.name not in allowed_names:
            continue
        validator_for(remote.input_schema).check_schema(remote.input_schema)
        qualified_name = f"{server_id}_{remote.name}"

        async def handler(
            tool_call_id: str,
            arguments: dict[str, Any],
            remote_name: str = remote.name,
        ) -> dict[str, Any]:
            """调用原始 MCP 工具名，并将远端结果归一化为 Host Payload。"""
            response = await client.call_tool(remote_name, arguments)
            return result_payload(response)

        definitions[qualified_name] = ToolDefinition(
            name=qualified_name,
            description=remote.description or "",
            input_schema=remote.input_schema,
            handler=handler,
        )
    return definitions


async def run_agent(
    provider: LLMProvider,
    runtime: ToolRuntime,
    tools: dict[str, ToolDefinition],
    user_input: str,
    max_rounds: int = 4,
    max_tool_calls: int = 8,
) -> str:
    """有限轮次内回传每个调用的结果；原生消息不重新拼装。"""
    if max_rounds < 1 or max_tool_calls < 1:
        raise ValueError("轮次与工具调用预算必须为正整数")
    messages: list[dict[str, Any]] = [{"role": "user", "content": user_input}]
    model_tools = [tool.to_model_tool() for tool in tools.values()]
    tool_calls_used = 0

    for round_no in range(1, max_rounds + 1):
        reply = await provider.complete(messages, model_tools)
        if reply.message is None:
            raise RuntimeError("MODEL_REPLY_INVALID")
        messages.append(reply.message)
        if not reply.tool_calls and reply.text and reply.text.strip():
            print("LOOP", round_no, "final")
            return reply.text
        if not reply.tool_calls:
            raise RuntimeError("MODEL_REPLY_INVALID")
        # 先检查整批调用，避免超预算时已经执行了一部分副作用。
        if tool_calls_used + len(reply.tool_calls) > max_tool_calls:
            raise RuntimeError("MAX_TOOL_CALLS_EXCEEDED")
        for call in reply.tool_calls:
            tool_calls_used += 1
            print("LOOP", round_no, "tool_call", call.name)
            tool_result = await runtime.execute(call, tools)
            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": call.id,
                    "content": json.dumps(tool_result, ensure_ascii=False),
                }
            )
            runtime.trace.append(
                {"event": "result_written_to_context", "round": round_no, "tool_call_id": call.id}
            )

    raise RuntimeError("MAX_ROUNDS_EXCEEDED")


async def main(live: bool = False) -> None:
    """启动本地订单 Server，并执行协议契约检查及可选的真实 Agent Loop。"""
    parameters = StdioServerParameters(
        command=sys.executable,
        args=[str(base_dir / "mcp_server_v1.py")],
        cwd=base_dir,
    )

    async with Client(stdio_client(parameters)) as client:
        tools = await discover_tools(client, "orders", allowed_names={"get_order"})
        resources = await client.list_resources()
        prompts = await client.list_prompts()

        print("PROTOCOL", client.protocol_version)
        print("TOOLS", sorted(tools))
        print("RESOURCES", [str(item.uri) for item in resources.resources])
        print("PROMPTS", [item.name for item in prompts.prompts])

        runtime = ToolRuntime()
        success = await runtime.execute(
            ToolCall("call_success", "orders_get_order", {"order_id": "ord_1001"}),
            tools,
        )
        assert success["ok"] is True
        print("CONTRACT SUCCESS", success["status"])

        rejected = await runtime.execute(
            ToolCall("call_reject", "orders_get_order", {}),
            tools,
        )
        assert rejected["code"] == "INVALID_ARGUMENT"
        print("REJECT", rejected["code"])

        failed = await runtime.execute(
            ToolCall(
                "call_fail",
                "orders_get_order",
                {"order_id": "ord_missing"},
            ),
            tools,
        )
        assert failed["code"] == "MCP_TOOL_ERROR"
        print("FAIL", failed["code"])

        if not live:
            print("LIVE SKIP：使用 --live 显式运行真实 Agent Loop")
            print(json.dumps(runtime.trace, ensure_ascii=False, indent=2))
            return

        provider = DeepSeekProvider()
        try:
            answer = await run_agent(
                provider=provider,
                runtime=runtime,
                tools=tools,
                user_input=(
                    "先查询订单 ord_missing；如果工具明确返回订单不存在，"
                    "再查询 ord_1002，并告诉我最终查到的订单状态。"
                ),
            )
        finally:
            await provider.client.close()
        print("LIVE", answer)
        print(json.dumps(runtime.trace, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="订单 MCP Host：默认离线契约检查")
    parser.add_argument("--live", action="store_true", help="使用官方 DeepSeek 执行模型循环")
    asyncio.run(main(live=parser.parse_args().live))
