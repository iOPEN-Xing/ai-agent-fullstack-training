from __future__ import annotations

import json
import re
from typing import Any

from jsonschema import SchemaError, ValidationError, validate
from jsonschema.validators import validator_for

from app.core.errors import GatewayError, StructuredOutputError

_FENCE = re.compile(r"^\s*```(?:json)?\s*(.*?)\s*```\s*$", re.DOTALL | re.IGNORECASE)


def schema_from_request(api: str, body: dict[str, Any]) -> dict[str, Any] | None:
    """提取并校验调用方的 Schema；请求错误不能等模型生成后才发现。"""
    param = "response_format" if api == "chat" else "text.format"
    if api == "chat":
        output_format = body.get("response_format")
    else:
        output_format = (body.get("text") or {}).get("format")
    if output_format is None:
        return None
    if not isinstance(output_format, dict):
        raise invalid_schema(param, "Output format must be an object")
    if output_format.get("type") != "json_schema":
        return None

    definition = output_format.get("json_schema") if api == "chat" else output_format
    if not isinstance(definition, dict) or not isinstance(definition.get("schema"), dict):
        raise invalid_schema(param, "JSON Schema must be an object")
    schema = definition["schema"]
    # validator_for 会先以 $schema 查找方言；数组/对象不能作为映射键。
    if "$schema" in schema and not isinstance(schema["$schema"], str):
        raise invalid_schema(param, "$schema must be a string")
    try:
        # 按 $schema 选择方言；空对象 {} 也是有效 Schema，不可用 truthiness 跳过。
        validator_for(schema).check_schema(schema)
    except SchemaError as exc:
        raise invalid_schema(param, exc.message) from exc
    return schema


def invalid_schema(param: str, message: str) -> GatewayError:
    return GatewayError(
        message,
        status_code=422,
        error_type="invalid_request_error",
        code="invalid_json_schema",
        param=param,
    )


def content_from_response(api: str, payload: dict[str, Any]) -> str:
    try:
        if api == "chat":
            content = payload["choices"][0]["message"]["content"]
            if isinstance(content, str):
                return content
        else:
            if isinstance(payload.get("output_text"), str):
                return payload["output_text"]
            for output in payload.get("output", []):
                for item in output.get("content", []):
                    if item.get("type") in {"output_text", "text"} and isinstance(item.get("text"), str):
                        return item["text"]
    except (KeyError, IndexError, TypeError):
        pass
    raise StructuredOutputError("Could not find textual model output to validate")


def validate_response(api: str, payload: dict[str, Any], schema: dict[str, Any]) -> Any:
    content = content_from_response(api, payload)
    fenced = _FENCE.match(content)
    if fenced:
        content = fenced.group(1)
    try:
        parsed = json.loads(content)
    except json.JSONDecodeError as exc:
        raise StructuredOutputError(
            "Model output is not valid JSON",
            details={"line": exc.lineno, "column": exc.colno, "message": exc.msg},
        ) from exc
    try:
        validate(instance=parsed, schema=schema)
    except ValidationError as exc:
        raise StructuredOutputError(
            "Model output does not match the requested JSON Schema",
            details={"path": list(exc.absolute_path), "message": exc.message},
        ) from exc
    return parsed


def repair_instruction(error: StructuredOutputError, schema: dict[str, Any]) -> str:
    return (
        "Your previous response failed JSON Schema validation. Return only corrected JSON, "
        "with no Markdown fences or explanation.\n"
        f"Validation error: {error.message}; details={json.dumps(error.details, ensure_ascii=False)}\n"
        f"Required schema: {json.dumps(schema, ensure_ascii=False)}"
    )
