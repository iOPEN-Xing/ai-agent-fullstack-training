"""可运行的三层输出校验：原生格式约束、类型约束、业务组合约束。"""
from __future__ import annotations

import argparse
import json
import os
from collections.abc import Callable
from typing import Literal

import httpx
from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator


class AgentDecision(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    action: Literal["search_docs", "finish"]
    query: str | None = Field(..., min_length=1, max_length=200)
    answer: str | None = Field(..., min_length=1, max_length=4000)

    @model_validator(mode="after")
    def check_action_fields(self) -> AgentDecision:
        if self.action == "search_docs" and (not self.query or self.answer is not None):
            raise ValueError("search_docs 必须有 query，answer 必须为 null")
        if self.action == "finish" and (not self.answer or self.query is not None):
            raise ValueError("finish 必须有 answer，query 必须为 null")
        return self


class DecisionResult(BaseModel):
    status: Literal["ok", "failed"]
    decision: AgentDecision | None = None
    repair_attempts: int = 0
    issues: list[dict] = Field(default_factory=list)


ModelCall = Callable[[list[dict[str, str]]], str]


def decide(question: str, model_call: ModelCall, *, repair_attempts: int = 1) -> DecisionResult:
    if not 0 <= repair_attempts <= 3:
        raise ValueError("repair_attempts 必须在 0 到 3 之间")
    messages = [
        {"role": "system", "content": (
            "你是知识库决策器。没有政策资料时返回 search_docs 和搜索 query；"
            "有充分证据时返回 finish 和 answer。只返回 JSON，另一字段必须为 null。"
        )},
        {"role": "user", "content": question},
    ]
    for attempt in range(repair_attempts + 1):
        # 传输错误交给调用方处理；格式纠错不承担网络重试，否则可能放大调用次数。
        raw = model_call(messages)
        try:
            decision = AgentDecision.model_validate_json(raw)
            return DecisionResult(status="ok", decision=decision, repair_attempts=attempt)
        except ValidationError as exc:
            issues = exc.errors(include_url=False, include_input=False, include_context=False)
            if attempt == repair_attempts:
                return DecisionResult(status="failed", repair_attempts=attempt, issues=issues)
            messages.extend([
                {"role": "assistant", "content": raw},
                {"role": "user", "content": "校验失败，请修正 JSON：" + json.dumps(issues, ensure_ascii=False)},
            ])
    raise AssertionError("unreachable")


def call_deepseek(messages: list[dict[str, str]]) -> str:
    key = os.environ.get("DEEPSEEK_API_KEY", "").strip()
    if not key or key.startswith("replace-"):
        raise ValueError("请设置 DEEPSEEK_API_KEY")
    # 当前 Chat 的 json_object 只约束 JSON 语法；原生 Schema 示例使用 Responses。
    with httpx.Client(timeout=60, trust_env=False) as client:
        response = client.post("https://api.deepseek.com/v1/responses", headers={
            "Authorization": f"Bearer {key}",
        }, json={
            "model": os.environ.get("DEEPSEEK_MODEL", "").strip() or "deepseek-flash",
            "input": messages, "reasoning": {"effort": "none"}, "max_output_tokens": 800,
            "text": {"format": {"type": "json_schema", "name": "agent_decision", "strict": True,
                                "schema": AgentDecision.model_json_schema()}},
        })
    if response.status_code != 200:
        raise RuntimeError(f"DeepSeek Responses: HTTP {response.status_code}")
    data = response.json()
    if data.get("status") != "completed":
        raise RuntimeError(f"DeepSeek Responses 未完成：{data.get('status')}")
    return "".join(block["text"] for item in data.get("output", [])
                   for block in item.get("content", []) if block.get("type") == "output_text")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("question", nargs="?", default="公司差旅报销需要什么材料？")
    parser.add_argument("--repair-attempts", type=int, choices=range(4), default=1)
    args = parser.parse_args()
    result = decide(args.question, call_deepseek, repair_attempts=args.repair_attempts)
    print(result.model_dump_json(indent=2))
    # search_docs 只是已校验的决策；工具执行属于第二周 Runtime，不在本示例隐式执行。
    raise SystemExit(0 if result.status == "ok" else 1)


if __name__ == "__main__":
    main()
