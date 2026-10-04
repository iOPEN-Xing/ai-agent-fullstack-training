"""官网小额联调：验证当前账户与协议，不代表长程 Agent 已验收。"""
from __future__ import annotations

import argparse
import json
import os
from datetime import datetime, timezone
from pathlib import Path

import httpx

BASE_URL = "https://api.deepseek.com/v1"
MODEL = "deepseek-flash"
PERSON_SCHEMA = {
    "type": "object",
    "properties": {"name": {"type": "string"}, "age": {"type": "integer"}},
    "required": ["name", "age"], "additionalProperties": False,
}


def verify() -> dict:
    key = os.environ.get("DEEPSEEK_API_KEY", "").strip()
    if not key or key.startswith("replace-"):
        raise RuntimeError("请在被忽略的 .env 中配置 DEEPSEEK_API_KEY")
    if os.environ.get("DEEPSEEK_MODEL", MODEL).strip() != MODEL:
        raise RuntimeError("本次验收固定使用 deepseek-flash，请检查 DEEPSEEK_MODEL")
    configured_url = os.environ.get("DEEPSEEK_BASE_URL", BASE_URL).rstrip("/")
    if configured_url not in ("https://api.deepseek.com", BASE_URL):
        raise RuntimeError("本次验收只允许 DeepSeek 官方地址")
    evidence = []
    # trust_env=False 禁止本机 HTTP(S)_PROXY 改写此验收的传输路径；不启用重试。
    with httpx.Client(timeout=60, trust_env=False) as client:
        headers = {"Authorization": f"Bearer {key}"}

        def post(label, path, body, *, anthropic=False):
            url = "https://api.deepseek.com/anthropic/v1/messages" if anthropic else BASE_URL + path
            auth = {"x-api-key": key, "anthropic-version": "2023-06-01"} if anthropic else headers
            response = client.post(url, headers=auth, json=body)
            if response.status_code != 200:
                # 不输出请求头、密钥或完整 SDK 错误对象。
                raise RuntimeError(f"{label}: HTTP {response.status_code}")
            data = response.json()
            evidence.append({"check": label, "http_status": 200,
                             "model": data.get("model"), "usage": data.get("usage")})
            return data

        response = client.get(BASE_URL + "/models", headers=headers)
        response.raise_for_status()
        assert MODEL in [item["id"] for item in response.json()["data"]]
        evidence.append({"check": "model_catalog", "http_status": 200, "model": MODEL})
        common = {"model": MODEL, "max_tokens": 384, "thinking": {"type": "disabled"}}
        prompt = [{"role": "user", "content": "提取 Ada，36 岁，以 JSON 返回 name 和 age。"}]
        chat = post("chat", "/chat/completions", {
            **common, "messages": [{"role": "user", "content": "仅回复：连接成功"}],
        })
        assert "连接成功" in chat["choices"][0]["message"]["content"]
        data = post("json_object", "/chat/completions", {
            **common, "messages": prompt, "response_format": {"type": "json_object"},
        })
        assert json.loads(data["choices"][0]["message"]["content"]) == {"name": "Ada", "age": 36}
        # 协议名相同不等于能力相同。记录 Chat 的 Schema 子集，后续升级也可发现变化。
        response = client.post(BASE_URL + "/chat/completions", headers=headers, json={
            **common, "messages": prompt, "response_format": {
                "type": "json_schema", "json_schema": {
                    "name": "person", "strict": True, "schema": PERSON_SCHEMA,
                },
            },
        })
        assert response.status_code in (200, 400), f"chat_json_schema: HTTP {response.status_code}"
        if response.status_code == 200:
            assert json.loads(response.json()["choices"][0]["message"]["content"]) == {"name": "Ada", "age": 36}
        row = {"check": "chat_json_schema_capability", "http_status": response.status_code,
               "supported": response.status_code == 200}
        if response.status_code == 400:
            error = response.json().get("error", {})
            message = error.get("message", "").lower()
            assert "response_format" in message and any(
                word in message for word in ("unavailable", "unsupported", "not supported")
            ), "Chat Schema 请求被拒绝，但原因不是已识别的能力限制"
            row["rejection_code"] = error.get("code")
            row["rejection_reason"] = error.get("message", "").split("(request_id:")[0].strip()
        evidence.append(row)
        data = post("responses_schema", "/responses", {
            "model": MODEL, "input": prompt[0]["content"], "max_output_tokens": 384,
            "reasoning": {"effort": "none"},
            "text": {"format": {"type": "json_schema", "name": "person", "strict": True,
                                "schema": PERSON_SCHEMA}},
        })
        text = "".join(block.get("text", "") for item in data["output"]
                       for block in item.get("content", []) if block.get("type") == "output_text")
        assert data["status"] == "completed" and json.loads(text) == {"name": "Ada", "age": 36}
        tools = [{"type": "function", "function": {"name": "add", "description": "加法",
                  "parameters": {"type": "object", "properties": {
                      "a": {"type": "integer"}, "b": {"type": "integer"}},
                      "required": ["a", "b"], "additionalProperties": False}}}]
        messages = [{"role": "user", "content": "必须调用 add 工具计算 2+3，随后仅回复结果。"}]
        call = post("tool_call", "/chat/completions", {**common, "messages": messages,
                    "tools": tools, "tool_choice": {"type": "function", "function": {"name": "add"}}})
        assistant = call["choices"][0]["message"]
        messages.append(assistant)  # 保留供应商附加字段，避免多轮协议丢失。
        calls = assistant.get("tool_calls", [])
        assert len(calls) == 1 and calls[0]["function"]["name"] == "add"
        args = json.loads(calls[0]["function"]["arguments"])
        assert args == {"a": 2, "b": 3}
        messages.append({"role": "tool", "tool_call_id": calls[0]["id"], "content": "5"})
        final = post("tool_result", "/chat/completions", {**common, "messages": messages,
                     "tools": tools, "tool_choice": "none"})
        assert "5" in final["choices"][0]["message"]["content"]
        body = {**common, "messages": [{"role": "user", "content": "仅回复：流式成功"}],
                "stream": True, "stream_options": {"include_usage": True}}
        text, done, usage = "", False, None
        with client.stream("POST", BASE_URL + "/chat/completions", headers=headers, json=body) as stream:
            if stream.status_code != 200:
                raise RuntimeError(f"chat_sse: HTTP {stream.status_code}")
            for line in stream.iter_lines():
                if not line.startswith("data:"):
                    continue
                payload = line[5:].strip()
                if payload == "[DONE]":
                    done = True
                    continue
                chunk = json.loads(payload)
                assert "error" not in chunk
                usage = chunk.get("usage") or usage
                for choice in chunk.get("choices", []):
                    text += choice["delta"].get("content") or ""
        assert done and "流式成功" in text
        evidence.append({"check": "chat_sse", "http_status": 200, "model": MODEL, "usage": usage})
        data = post("anthropic_messages", "", {
            **common, "messages": [{"role": "user", "content": "仅回复：兼容成功"}],
        }, anthropic=True)
        assert "兼容成功" in "".join(block.get("text", "") for block in data["content"])
    return {"checked_at": datetime.now(timezone.utc).isoformat(),
            "endpoint": BASE_URL, "model": MODEL, "checks": evidence}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, help="保存无密钥的联调证据 JSON")
    args = parser.parse_args()
    result = verify()
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
