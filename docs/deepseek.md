# DeepSeek 官方直连接入

本 fork 的课程示例默认模型为 `deepseek-flash`。2026-10-04 已通过官方模型列表和实际请求核对；旧名称 `deepseek-v4-flash` 是兼容别名。模型名称变更依据 [DeepSeek 更新记录](https://api-docs.deepseek.com/updates/)，接口参数以对应协议的官方文档为准。

## 一份本机配置

在仓库根目录复制 `.env.example` 为 `.env`，用编辑器填写密钥：

```dotenv
DEEPSEEK_API_KEY=replace-with-your-deepseek-api-key
DEEPSEEK_MODEL=deepseek-flash
DEEPSEEK_BASE_URL=https://api.deepseek.com/v1
COMMERCE_MODEL_PROVIDER=deepseek
```

真实密钥只写入被 Git 忽略的 `.env`。上面的值都是占位值；`DEEPSEEK_API_KEY` 没有可用的默认值。

| 入口 | 配置如何进入进程 | 地址约定 |
| --- | --- | --- |
| 六个 TypeScript Agent 的 `npm start` | shell 变量优先；随后本项目 `.env` 优先于根 `.env` | 只接受 `https://api.deepseek.com` 和 `/v1`，统一为 `/v1` |
| 根 `make check-live` | uv 的 `--env-file .env`；shell 变量优先 | 检查官方地址，接受官方根路径或 `/v1` |
| 完整 Structured Output 示例 | 同上；读取 key/model | 固定 `https://api.deepseek.com/v1/responses`，不读取 `DEEPSEEK_BASE_URL` |
| MCP 模型入口 | 只读进程环境；uv 从根目录用 `--env-file "$PWD/.env"` 显式加载 | 只接受官方根路径或 `/v1`；完整 Host 要加 `--live` |
| 早期 Python 示例 | 只读取已导出的进程环境；模型默认值写在示例中 | 课程默认官方地址，个别原型保留可配置的供应商地址 |
| Commerce 本地示例 | shell、行业 `.env`、Commerce 根 `.env`，按这个顺序填缺项 | `deepseek` 配置固定 Anthropic 兼容地址 |
| 1-7 Gateway | YAML 引用进程环境；使用自己的 `.env` | YAML 的供应商地址不带 `/v1`，客户端再追加路径 |

Node 的 `.env` 在 `start` 和真实 `lab:cycle` 脚本中加载；`npm test` 和离线 `lab:harness` 不加载密钥文件。修改配置后重启进程。六个项目独立编译，因此各自保留 `src/model.ts`，没有引入跨目录共享模块。

## 协议选择

官网直连表示请求目标是 `api.deepseek.com`。项目使用三种协议格式，并不需要三个供应商账户。

| 场景 | URL | 本 fork 用法 |
| --- | --- | --- |
| 普通对话、工具循环、流式输出 | `https://api.deepseek.com/v1/chat/completions` | OpenAI Chat 兼容格式；六个 pi Agent 使用此入口 |
| 原生 Schema 输出 | `https://api.deepseek.com/v1/responses` | `text.format`、`reasoning.effort`；完整结构化示例使用此入口 |
| Commerce 的本地手写 Loop | `https://api.deepseek.com/anthropic/v1/messages` | 保留 Anthropic SDK 和现有工具协议，改变官方地址、模型和鉴权 |

2026-10-04 [联调记录](verification.md#真实官方接口)中，Chat `json_object` 返回合法 JSON，`response_format: json_schema` 返回 HTTP 400，错误明确指向格式类型当前不可用；Responses 的 `text.format: json_schema` 返回 HTTP 200。该结论限于本次账户、样例和日期；官方接口更新后需重新联调。不要把“OpenAI compatible”理解为支持所有 OpenAI 参数。复查当前账户可执行 `make check-live`，脚本会记录 Chat Schema 能力是否变化。协议说明见 [JSON Output](https://api-docs.deepseek.com/guides/json_mode/)和 [Responses API](https://api-docs.deepseek.com/api/create-response/)。

JSON 格式正确仍可能缺字段、用错类型或违反业务规则。完整示例在原生 Schema 之后使用 Pydantic 严格类型和动作组合校验；默认最多纠错一次（`--repair-attempts 0..3` 可调整），仍失败时返回 `status: failed`，不把无效结果当作成功，也不执行搜索工具。本示例当前由 Pydantic 生成的 Schema 已实测通过；修改字段后需重新核对供应商接受的 Schema 子集。

## 运行入口

以下命令均在仓库根目录执行。

```bash
# 使用 Gateway 的锁定 Python 依赖执行小额协议联调。
make check-live

# 第一周完整输出校验示例，默认输入是没有资料的报销问题。
uv run --env-file .env --project course_code/week01/1-7/llm-gateway --locked \
  python course_code/week01/1-5/deepseek_structured_demo.py

# 第三周完整 Harness：默认创建临时工作区，等待具体补丁审批。
npm --prefix course_code/week03/3-5/harness_agent start

# 第二周完整 MCP Host：只读订单查询，显式开启真实模型。
uv run --env-file "$PWD/.env" --directory course_code/week02/2-3 --locked \
  python mcp_host_v1.py --live
```

输出校验示例正常会返回 `search_docs` 决策和 query；它表示下一步需要检索，不能把它当作已有政策答案。该示例依赖 HTTPX 和 Pydantic，复用已锁定的 Gateway 环境；早期 OpenAI SDK 示例需另外安装 SDK，见[课程指南](course-guide.md)。

MCP 使用自己的锁定环境，默认不带 `--live` 时只执行离线契约。uv 的 `--directory` 改变运行目录，因此 `.env` 要先用根目录的 `$PWD` 定位。按函数阅读与失败语义见 [MCP Host 链路](mcp-host.md)。

### 思考模式与多轮工具

课程 Chat 示例显式发送 `thinking: {type: disabled}`，Responses 使用 `reasoning: {effort: none}`。这是为了让有限输出预算用于可见结果，并使基础工具循环更容易观察。DeepSeek 默认启用思考；仅省略字段会改变运行行为。[官方思考模式说明](https://api-docs.deepseek.com/guides/thinking_mode/)。

pi 的模型配置中 `reasoning: true` 声明模型有思考能力；当调用没有指定 `reasoningEffort` 时，当前 pi 适配器发送 `thinking: disabled`。同时设置 `thinkingFormat: deepseek`、`maxTokensField: max_tokens` 和推理字段回传兼容项。离线连接测试核对真实请求体、鉴权头、官方 URL 和 SSE 结果，不只检查配置常量。

若以后启用思考，必须保存并回传供应商要求的 `reasoning_content`；不要只重建 assistant 的普通文字和工具调用。工具结果还必须使用原 `tool_call_id`。丢失这些字段可能导致下一轮请求被拒绝。

`contextWindow: 128000` 和 `maxTokens: 4096` 是课程在 pi 层声明的预算，不是 DeepSeek 最大能力承诺，也不表示已经实现自动摘要。成本字段的 0 是本地类型占位，不能理解为 API 免费。需要修改预算时同时验证上下文增长、输出截断和完成判定。

## Gateway 是另一条调用路径

1-7 Gateway 的默认 YAML 现在只配置 DeepSeek 官方上游，`smart` 和 `fast` 两个公开别名都指向 `deepseek-flash`。这是最少配置的可运行示例，两个别名不会产生性能差异，也没有第二供应商可供 fallback。优先级、加权轮询和故障转移能力由 Mock 测试覆盖；实际使用多路由时要另行联调。

Gateway 调用方使用 `GATEWAY_API_KEY`；服务端访问供应商使用 `DEEPSEEK_API_KEY`，两者不能互换。当前六个 Agent 直接持有 DeepSeek 密钥，不调用本地 Gateway。需要实验网关时按 [Gateway README](../course_code/week01/1-7/llm-gateway/README.md) 使用 SDK 或 curl；不要把 `DEEPSEEK_BASE_URL` 改成 localhost，它会在 Agent 启动时被拒绝。

## Commerce 本地 Messages 示例

Commerce 根目录指 `course_code/week03/3-5/commerce-agents`，不同于训练营仓库根目录。可在训练营根目录用 uv 显式加载配置：

```bash
# 安装已完成后，启动零售 API。需要保留此终端进程。
uv run --env-file .env --no-project \
  --python course_code/week03/3-5/commerce-agents/.venv/bin/python \
  python -m uvicorn retail.api.main:app \
  --app-dir course_code/week03/3-5/commerce-agents/examples --port 8000
```

未设置 `COMMERCE_MODEL_PROVIDER` 时保留原 Anthropic 路径；根配置模板显式选择 DeepSeek。`COMMERCE_MODEL_PROVIDER=deepseek` 在客户端创建前，设置 `ANTHROPIC_BASE_URL=https://api.deepseek.com/anthropic`，把 `DEEPSEEK_API_KEY` 传给 SDK 的 `ANTHROPIC_API_KEY` 并移除旧 `ANTHROPIC_AUTH_TOKEN`。主 Loop、记忆提取和 Merchant 分析委派都显式使用 `deepseek-flash`，没有依赖 Claude 模型名自动映射。兼容协议支持范围见 [DeepSeek Anthropic API](https://api-docs.deepseek.com/guides/anthropic_api/)。

该配置关闭思考、Web Search 和托管 Code Execution。业务工具、主机审批、变更账本和 SQL 分析仍由原 Runtime 处理。`COMMERCE_DEMO_AUTH=sdk` 与此配置不兼容，启动时明确报错。四个行业工厂都有离线回归测试；本次只对零售 Shopping 和 Merchant 做真实模型单轮验证。

Commerce 的 Agent SDK 控制台、Managed Agents 和 MCP 托管部署材料保留原 Anthropic 路径，未迁移到 DeepSeek。改变 `base_url` 不能自动替换托管平台、OAuth、服务端工具或定时作业。

## 定位常见失败

| 现象 | 先检查什么 | 处理方式 |
| --- | --- | --- |
| 401 或缺密钥 | shell 是否导出旧值、`.env` 是否在当前入口读取范围内 | 更新正确来源并重启；不要打印完整环境变量 |
| 400 格式错误 | 请求使用 Chat 还是 Responses，Schema 字段属于哪种协议 | 原生 Schema 使用 Responses；Chat JSON 模式仍需本地校验 |
| 下一轮工具请求被拒绝 | assistant 附加字段和工具 ID 是否完整回传 | 保存供应商消息对象，逐一配对 Tool Result |
| 输出为空或被截断 | 终止原因、输出预算、是否默认启用思考 | 根据原因调整预算；不把空输出或 incomplete 当作成功 |
| 429、连接超时 | 当前账户限额、网络和超时配置 | 有限退避；保留任务状态，不反复重放有副作用的工具 |
| 改了地址却没有经过 Gateway | Agent 配置是官方直连 | 用 Gateway 自己的示例客户端验证网关能力 |
