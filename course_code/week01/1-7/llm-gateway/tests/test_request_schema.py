from __future__ import annotations

import json

import httpx
import pytest

from tests.conftest import gateway_client, make_config


@pytest.mark.asyncio
@pytest.mark.parametrize("api", ["chat", "responses"])
@pytest.mark.parametrize("stream", [False, True])
@pytest.mark.parametrize(
    "definition",
    [
        {},
        {"schema": None},
        {"schema": []},
        {"schema": {"type": "not-a-json-type"}},
        {"schema": {"properties": {"name": {"type": 123}}}},
        {"schema": {"$schema": {}}},
        {"schema": {"$schema": []}},
    ],
)
async def test_invalid_schema_is_rejected_before_upstream(tmp_path, auth_headers, api, stream, definition):
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": "{}"}}], "output_text": "{}"},
        )

    if api == "chat":
        endpoint = "/v1/chat/completions"
        body = {
            "model": "smart",
            "messages": [{"role": "user", "content": "hello"}],
            "response_format": {"type": "json_schema", "json_schema": definition},
        }
        param = "response_format"
    else:
        endpoint = "/v1/responses"
        body = {"model": "smart", "input": "hello", "text": {"format": {"type": "json_schema", **definition}}}
        param = "text.format"
    body["stream"] = stream

    async with gateway_client(make_config(tmp_path / "gateway.db"), handler) as client:
        response = await client.post(endpoint, headers=auth_headers, json=body)

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "invalid_json_schema"
    assert response.json()["error"]["param"] == param
    assert calls == []


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("endpoint", "body", "param"),
    [
        (
            "/v1/chat/completions",
            {
                "model": "smart",
                "messages": [],
                "response_format": {"type": "json_schema", "json_schema": "invalid"},
            },
            "response_format",
        ),
        ("/v1/responses", {"model": "smart", "input": "hello", "text": {"format": "invalid"}}, "text.format"),
    ],
)
async def test_malformed_format_returns_client_error(tmp_path, auth_headers, endpoint, body, param):
    def handler(_: httpx.Request) -> httpx.Response:
        raise AssertionError("Invalid format must not reach the upstream")

    async with gateway_client(make_config(tmp_path / "gateway.db"), handler) as client:
        response = await client.post(endpoint, headers=auth_headers, json=body)

    assert response.status_code == 422
    assert response.json()["error"]["param"] == param


@pytest.mark.asyncio
@pytest.mark.parametrize("schema", [{}, {"type": "object", "properties": {"name": {"type": "string"}}}])
async def test_valid_schema_is_forwarded_unchanged(tmp_path, auth_headers, schema):
    def handler(request: httpx.Request) -> httpx.Response:
        assert json.loads(request.content)["response_format"]["json_schema"]["schema"] == schema
        return httpx.Response(200, json={"choices": [{"message": {"content": '{"name":"Ada"}'}}]})

    async with gateway_client(make_config(tmp_path / "gateway.db"), handler) as client:
        response = await client.post(
            "/v1/chat/completions",
            headers=auth_headers,
            json={
                "model": "smart",
                "messages": [{"role": "user", "content": "Name"}],
                "response_format": {
                    "type": "json_schema", "json_schema": {"name": "person", "schema": schema}
                },
            },
        )
    assert response.status_code == 200
