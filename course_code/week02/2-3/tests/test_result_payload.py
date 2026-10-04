import json
from types import SimpleNamespace

import pytest
from mcp_client_v1 import result_payload


def response(*texts, is_error=False, structured=None):
    return SimpleNamespace(
        is_error=is_error,
        structured_content=structured,
        content=[SimpleNamespace(text=text) for text in texts],
    )


def test_empty_remote_error_is_reported_without_indexing_missing_content():
    result = result_payload(response(is_error=True))
    assert result["ok"] is False and result["code"] == "MCP_TOOL_ERROR"


def test_all_text_blocks_are_preserved_in_order():
    assert result_payload(response("first", "second")) == {"ok": True, "text": "first\nsecond"}


@pytest.mark.parametrize("value", [[1, 2], "order", 42, {"amount": float("nan")}])
def test_non_object_or_non_json_remote_payload_is_a_structured_failure(value):
    result = result_payload(response(structured=value))
    assert result["ok"] is False and result["code"] == "MCP_RESULT_INVALID"


@pytest.mark.parametrize("is_error", [False, True])
def test_oversized_success_and_error_content_obey_the_same_limit(is_error):
    result = result_payload(response("x" * 300, is_error=is_error), max_chars=128)
    assert result["code"] == "RESULT_TOO_LARGE"
    assert len(json.dumps(result, ensure_ascii=False)) <= 128


def test_remote_business_failure_is_preserved():
    payload = {"ok": False, "code": "ORDER_NOT_FOUND"}
    assert result_payload(response(structured=payload)) == payload
