import json

import pytest
from deepseek_structured_demo import AgentDecision, decide
from pydantic import ValidationError


def test_business_rule_rejects_shape_correct_but_invalid_decision():
    with pytest.raises(ValidationError):
        AgentDecision.model_validate_json('{"action":"finish","query":null,"answer":null}')


def test_repairs_invalid_output_once_and_returns_valid_decision():
    replies = iter(['{"action":"finish"', '{"action":"finish","query":null,"answer":"需要发票。"}'])
    contexts = []

    def model_call(messages):
        contexts.append([dict(item) for item in messages])
        return next(replies)

    result = decide("报销需要什么？", model_call, repair_attempts=1)
    assert result.status == "ok" and result.repair_attempts == 1
    assert result.decision.answer == "需要发票。"
    assert len(contexts) == 2
    assert contexts[1][-2]["role"] == "assistant"
    assert "校验失败" in contexts[1][-1]["content"]


def test_exhausted_repair_returns_explicit_failure_without_a_decision():
    calls = []
    result = decide("问题", lambda messages: calls.append(messages) or "not json", repair_attempts=2)
    assert len(calls) == 3
    assert result.status == "failed" and result.decision is None
    assert result.repair_attempts == 2 and result.issues


def test_transport_error_does_not_enter_semantic_repair():
    calls = []

    def model_call(messages):
        calls.append(messages)
        raise RuntimeError("upstream timeout")

    with pytest.raises(RuntimeError, match="upstream timeout"):
        decide("问题", model_call)
    assert len(calls) == 1


def test_search_decision_does_not_execute_a_tool():
    result = decide("查找政策", lambda _: json.dumps({
        "action": "search_docs", "query": "报销政策", "answer": None,
    }))
    assert result.status == "ok" and result.decision.action == "search_docs"
