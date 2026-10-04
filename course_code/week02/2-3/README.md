# MCP：从本地能力发现到模型工具循环

先运行没有模型的 Client/Server，再阅读 `loop_v1.py` 和 `mcp_host_v1.py`。四个文件是两层演示，不需要一起启动。

| 文件 | 作用 |
| --- | --- |
| `mcp_server_v1.py` | 注册订单工具、只读 Resource 和 Prompt；默认 stdio，也可用 `--http` |
| `mcp_client_v1.py` | 用同一 Python 解释器拉起 Server，发现工具并查询固定订单 |
| `loop_v1.py` | 将远端工具投影为 DeepSeek 的 Function Calling，回传结果 |
| `mcp_host_v1.py` | 分离 Provider 和 Host，补充名称、参数、内容大小等约束 |

文件名中的 `v1` 表示课堂示例版本。代码中的 `mcp.Client` / `MCPServer` 使用官方 SDK v2，不能安装 Commerce 固定的 SDK v1 环境后直接运行。[官方 SDK 安装说明](https://github.com/modelcontextprotocol/python-sdk/blob/main/docs/get-started/installation.md)。

在训练营仓库根目录执行，无需 API Key，也无需手动先启动 Server：

```bash
uv run --directory course_code/week02/2-3 --locked python mcp_client_v1.py
```

2026-10-04 实测发现 `get_order`、`create_ticket` 两个工具，查询 `ord_1001` 返回 `ok: True`、`status: pending`、`amount_cents: 2999`。`pyproject.toml` 声明依赖，`uv.lock` 固定直接与传递版本；这里使用独立环境，不修改 Commerce 的 SDK v1 依赖。

模型与 Host 所需的 OpenAI SDK、jsonschema 也在同一锁文件中。真实运行从仓库根加载 `.env`，并指定模型入口；具体命令和范围见 [DeepSeek 接入](../../../docs/deepseek.md)。

`result_payload` 将 MCP 结果转成业务对象：优先使用结构化内容，否则合并文本块；空错误、非法对象、非 JSON 值和超大结果都返回明确错误。预算按最终 JSON 字符数计算，默认 2000，错误结果同样受限。这里只归一化内容，不证明业务数据正确，也不执行下一步动作。

Server 的工单结果来自内存演示，没有真实持久化。远端 Tool Result 仍是不可信数据；MCP 的能力发现不能替代 Host 的授权、参数校验与结果校验。HTTP 模式、Resource/Prompt 读取和变更类工具未在本次 stdio 联调中验收。
