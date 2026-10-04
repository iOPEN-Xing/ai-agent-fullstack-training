# 沿一次订单查询理解 MCP Host

对应 [MCP 章节入口](../course_code/week02/2-3/README.md)。本章用本地订单服务解释协议与宿主边界，完整阅读路径是 `main → discover_tools → DeepSeekProvider.complete → run_agent → ToolRuntime.execute → result_payload`。默认 Host 只执行离线契约检查，`--live` 才访问模型。

`mcp_client_v1.py` 是无模型的协议入口，`loop_v1.py` 是较短的循环对照，`mcp_host_v1.py` 是完整边界实现。独立 `pyproject.toml` 和 `uv.lock` 固定 SDK v2 及传递依赖；Commerce 的 SDK v1 环境不能混用。

## 能力发现

[`mcp_host_v1.py`](../course_code/week02/2-3/mcp_host_v1.py) 的 `discover_tools` 读取 Server 公布的工具，先筛选宿主明确传入的 `allowed_names`，再检查 Schema 本身是否合法。`ToolDefinition.to_model_tool` 将留下的定义投影成模型的 function tools。当前 `main` 只传入 `{"get_order"}`，即使 Server 同时公布 create_ticket，模型也得不到其执行能力。

模型使用 `orders_get_order`，处理器调用 Server 原名 `get_order`。前缀负责区分来源；它不提供远端身份认证。循环里的 handler 用默认参数绑定各自的 remote.name，避免所有闭包最后都指向同一个工具。

[`test_host_runtime.py`](../course_code/week02/2-3/tests/test_host_runtime.py) 检查白名单、名称转换与未注册工具拒绝；[`test_stdio_contract.py`](../course_code/week02/2-3/tests/test_stdio_contract.py) 用真实子进程验证工具发现、Resource 与 Prompt。Resource/Prompt 是可发现的数据和模板，本 Host 只枚举它们，没有自动放入模型上下文。

## 模型消息

同一 [Host 源码](../course_code/week02/2-3/mcp_host_v1.py) 中，`DeepSeekProvider.complete` 只负责模型协议：将 SDK 的完整 assistant 消息存入 `ModelReply.message`，将全部 Tool Call 按原顺序转成内部 `ToolCall`。参数 JSON 无效时保存为 None，让 Runtime 明确拒绝；不能把它默认为空对象并继续执行。

`run_agent` 直接保存原生 message。Tool Result 用原来的 tool_call_id 回传，原生附加字段也保留。模型同轮提出两个调用，就必须得到两条对应结果；只回第一条会留下未匹配调用。设置关闭思考并不构成丢弃原生字段的理由。

[`test_host_loop.py`](../course_code/week02/2-3/tests/test_host_loop.py) 使用真实 OpenAI SDK 和 HTTP Mock 检查实际请求体、官方 URL、关闭思考、1024 token 输出预算、两次调用与原生字段；另一项测试检查下一轮完整上下文。它验证请求和适配器行为，真实模型能否按任务完成则另外记录。

## 执行边界

[`ToolRuntime.execute`](../course_code/week02/2-3/mcp_host_v1.py) 按下列顺序执行。Trace 只记录宿主实际经过的阶段，不能从模型文字推断工具已执行。

| 顺序 | 检查或动作 | 失败结果 | 是否已调用 Server |
| --- | --- | --- | --- |
| 1 | 工具必须在注册表 | TOOL_NOT_FOUND | 否 |
| 2 | 参数必须是 JSON 对象 | INVALID_ARGUMENT | 否 |
| 3 | 用 jsonschema 校验完整参数 | INVALID_ARGUMENT | 否 |
| 4 | 记录 server_call，进入 10 秒超时范围 | TOOL_RESULT_UNKNOWN（超时或异常） | 已进入调用，结果待核查 |
| 5 | 归一化结果，绑定 Host 的关联 ID | 业务成功或明确业务错误 | 是 |
| 6 | 记录 tool_result，交给 Loop 回传 | 对应原 Tool Call | 是 |

结果合并顺序为 `{**result, "tool_call_id": call.id}`，业务字段无法覆盖宿主关联 ID。外层取消不会被普通 Exception 捕获，取消会继续传播；超时与断连则返回未知结果。未知不等于“没有副作用”，因此不自动重试，也不将可能带内部信息的传输异常直接交给模型。

[`test_host_runtime.py`](../course_code/week02/2-3/tests/test_host_runtime.py) 检查非法参数不进入处理器、伪造 ID 被覆盖、超时/断连只执行一次、异常信息不进入结果、取消继续传播。当前业务错误的 message 仍来自 Server；若接入外部服务，应按该服务的数据范围设计过滤，不把内容归一化当作授权或可信性证明。

## 结果归一化

[`mcp_client_v1.py`](../course_code/week02/2-3/mcp_client_v1.py) 中的 `result_payload` 是 Client 与两个 Loop 共用的协议边界。先处理 MCP 的 is_error；成功时优先使用结构化对象，否则把所有文本块按顺序合并。

| 输入 | 统一结果 |
| --- | --- |
| MCP 错误，无文本 | `ok=false`、MCP_TOOL_ERROR、通用说明 |
| MCP 错误，有多段文本 | 合并文本，仍为 MCP_TOOL_ERROR |
| 结构化字典，未给 ok | 保留业务字段，补 ok=true |
| 业务显式 ok=false | 保留业务失败，不改写成成功 |
| 结构化值非字典、ok 非布尔、非 JSON 值或 NaN | MCP_RESULT_INVALID |
| 无结构化值，有文本 | `ok=true` 和 text |
| 结果 JSON 超过字符预算 | RESULT_TOO_LARGE |

[`test_result_payload.py`](../course_code/week02/2-3/tests/test_result_payload.py) 对应空错误、多文本、结构化优先级、业务失败、非法值、NaN 和大小限制。默认预算为归一化结果 JSON 的 2000 个字符，错误与成功都受限；Host 的关联字段在此后添加。这不是网络字节限制，也不能阻止 SDK 在接收大响应时占用内存。没有内容的成功结果仍是空 text，不额外断言订单业务成功。

## 循环和预算

[`run_agent`](../course_code/week02/2-3/mcp_host_v1.py) 每轮完成三个动作：保存 assistant 消息、按顺序执行该轮调用、回传对应结果。无工具调用且有非空文本时结束；无文本也无调用时报 MODEL_REPLY_INVALID。

| 预算 | 当前默认 | 由谁决定 |
| --- | --- | --- |
| 模型轮次 | 4 | Host 调用 run_agent 时设置 |
| 累计工具调用 | 8，本地拒绝也计数 | Host；每批执行前整体检查 |
| 单工具调用 | 10 秒 | ToolRuntime |
| 模型输出 | 1024 token | Provider 请求 |
| SDK 请求超时 | 30 秒，自动重试 0 | Provider 客户端 |
| 结果内容 | 2000 个 JSON 字符 | result_payload |

一批 9 次调用会在任何处理器执行前报 MAX_TOOL_CALLS_EXCEEDED，避免执行一半后才发现超预算。用完 4 轮仍未得到最终文本时报 MAX_ROUNDS_EXCEEDED。预算限制不同资源，不能用轮数推导整项任务的严格总耗时；SDK 超时也包含传输库自身的阶段语义。

[`test_host_loop.py`](../course_code/week02/2-3/tests/test_host_loop.py) 检查整批预算拒绝、空回复失败和全部回传。Runtime trace 的 server_call 表示已开始尝试，tool_result 表示已得到归一化结果，result_written_to_context 表示已回写上下文；缺少后两者时不能凭第一项宣布成功。

## 一次成功与一次失败如何推进

真实任务先查 ord_missing，再在明确 ORDER_NOT_FOUND 后查询 ord_1002。2026-10-04 的官方模型运行用了 3 轮：第一次返回订单不存在，第二次查到 shipped、1599 分，第三次输出结果。变更查询目标是任务明确允许的下一步，不能把超时/断连也解释成订单不存在。

本地 Server 使用固定订单和内存工单结果，没有真实认证、数据库事务或工单持久化。当前完整入口只允许查询，尚未验收 HTTP 传输和工单变更。需要接入真实写业务时，先定义批准对象、幂等键、结果查询和权限来源，再增加明确的失败测试。完整命令见 [章节 README](../course_code/week02/2-3/README.md)，实际覆盖见 [验证记录](verification.md)。
