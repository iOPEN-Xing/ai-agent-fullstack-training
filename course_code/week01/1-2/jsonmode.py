import json
import os
from openai import OpenAI
from typing import Literal

from pydantic import BaseModel, Field, ValidationError


class AgentAction(BaseModel):
    # 同一类型定义用于生成提示中的 Schema 和本地校验，避免字段漂移。
    step: Literal["inspect_logs", "run_tests", "read_code", "ask_user"] = Field(
        description="Agent 下一步要执行的动作"
    )
    reason: str = Field(description="选择这个动作的原因")
    needs_user_input: bool = Field(description="是否需要向用户补充提问")
    confidence: float = Field(ge=0, le=1, description="当前判断的置信度，范围 0 到 1")

client = OpenAI(
    api_key=os.environ["DEEPSEEK_API_KEY"],
    base_url="https://api.deepseek.com",
    max_retries=0,
)

# 这里的 Schema 只写进提示词；json_object 不提供原生 Schema 约束。
schema = AgentAction.model_json_schema()

response = client.chat.completions.create(
    model="deepseek-flash",
    messages=[
        {
            "role": "system",
            "content": (
                "你是 Agent 决策器。必须输出 json。"
                "输出必须符合以下 JSON Schema：\n"
                f"{json.dumps(schema, ensure_ascii=False)}"
            ),
        },
        {
            "role": "user",
            "content": "目标：检查 tests/test_api.py 为什么失败。当前还没有测试日志。",
        },
    ],
    # JSON mode 约束 JSON 语法，字段、类型和业务含义仍需本地校验。
    response_format={"type": "json_object"},
    max_tokens=1024,
    extra_body={"thinking": {"type": "disabled"}},
)

raw_text = response.choices[0].message.content
if not raw_text:
    raise RuntimeError("MODEL_EMPTY_RESPONSE: 模型没有返回任何内容")

try:
    # 拒绝枚举和范围错误；这个示例未启用严格类型，也没有纠错或业务授权。
    action = AgentAction.model_validate_json(raw_text)
except ValidationError as exc:
    raise RuntimeError(f"MODEL_SCHEMA_INVALID: {exc}") from exc

print(action)
