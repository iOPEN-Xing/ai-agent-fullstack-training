# MCP：从本地能力发现到模型工具循环

先运行没有模型的 Client/Server，再阅读 `loop_v1.py` 和 `mcp_host_v1.py`。四个文件是两层演示，不需要一起启动。

逐函数、错误分支和测试对应关系见 [MCP Host 链路](../../../docs/mcp-host.md)。

| 文件 | 作用 |
| --- | --- |
| `mcp_server_v1.py` | 注册订单工具、只读 Resource 和 Prompt；默认 stdio，也可用 `--http` |
| `mcp_client_v1.py` | 用同一 Python 解释器拉起 Server，发现工具并查询固定订单 |
| `loop_v1.py` | 将远端工具投影为 DeepSeek 的 Function Calling，回传结果 |
| `mcp_host_v1.py` | 完整入口：白名单、完整 Schema 校验、超时、调用预算和逐个回传 |

文件名中的 `v1` 表示课堂示例版本。代码中的 `mcp.Client` / `MCPServer` 使用官方 SDK v2，不能安装 Commerce 固定的 SDK v1 环境后直接运行。[官方 SDK 安装说明](https://github.com/modelcontextprotocol/python-sdk/blob/main/docs/get-started/installation.md)。

在训练营仓库根目录执行，无需 API Key，也无需手动先启动 Server：

```bash
uv run --directory course_code/week02/2-3 --locked python mcp_client_v1.py
```

2026-10-04 实测发现 `get_order`、`create_ticket` 两个工具，查询 `ord_1001` 返回 `ok: True`、`status: pending`、`amount_cents: 2999`。`pyproject.toml` 声明依赖，`uv.lock` 固定直接与传递版本；这里使用独立环境，不修改 Commerce 的 SDK v1 依赖。

模型与 Host 所需的 OpenAI SDK、jsonschema 也在同一锁文件中。真实运行从仓库根加载 `.env`，并指定模型入口；具体命令和范围见 [DeepSeek 接入](../../../docs/deepseek.md)。

`result_payload` 将 MCP 结果转成业务对象：优先使用结构化内容，否则合并文本块；空错误、非法对象、非 JSON 值和超大结果都返回明确错误。预算按最终 JSON 字符数计算，默认 2000，错误结果同样受限。这里只归一化内容，不证明业务数据正确，也不执行下一步动作。

完整 Host 默认只做离线契约检查，即使环境已有密钥也不会访问模型：

```bash
uv run --directory course_code/week02/2-3 --locked python mcp_host_v1.py
make check-mcp

# 从仓库根加载 .env，显式启用真实模型；只允许 get_order。
uv run --env-file "$PWD/.env" --directory course_code/week02/2-3 --locked python mcp_host_v1.py --live
```

`loop_v1.py` 保留较短的单 Server 教学循环，手工参数检查只支持示例所需的部分 Schema。完整 Host 用 jsonschema 校验，按原始调用 ID 回传全部 Tool Result，保留原生 assistant 字段；默认最多 4 轮、8 次工具调用，每次工具调用 10 秒。超时/断连返回 `TOOL_RESULT_UNKNOWN`，不会自动重试或声称操作没发生。两个模型入口均显式关闭思考、限制输出 1024 token、设置 SDK 请求超时 30 秒并关闭 SDK 自动重试。

离线测试包括真实 stdio 工具发现、查询、远端错误、Resource/Prompt 读取，以及 HTTP Mock 下的模型请求与上下文回传；它们不需要密钥。Server 的工单结果来自内存实现，没有真实持久化。HTTP 模式和变更类工具未验收；MCP 的能力发现不能替代 Host 的授权。
