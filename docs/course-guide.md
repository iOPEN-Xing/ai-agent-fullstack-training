# 课程代码阅读与运行指南

目录顺序就是学习顺序，但同一章可能同时保存完整程序、讲解片段和历史产物。先选择与目标相符的入口，再读内部设计；不要一次安装全部依赖后递归运行所有 `.py`。

下表的“可运行”表示文件结构有独立入口，还需要安装对应依赖与配置。只有[验证记录](verification.md)列出的部分经过本轮实际验收。

## 第一周

| 章节 | 入口与材料 | 当前性质 | 建议关注点 |
| --- | --- | --- | --- |
| 1-1 | `agent_loop_demo.py`、`eval_runner.py`、`sandbox_runner.py` | 独立演示；模型调用需要密钥 | 手写决策协议、多轮工具与评测；宿主子进程执行并不等于隔离沙箱 |
| 1-2 | `chat.py`、`responses.py`、`jsonmode.py` | SDK 小程序 | 两种 API、终止原因、JSON 格式与本地类型校验 |
| 1-2 | `dsAdapter.py`、`OpenAIAdapter.py`、`loop1.py` | 讲解片段；缺少公共类型和装配 | Adapter 的能力声明与错误归一化；不能直接启动 |
| 1-3 | `stream_deepseek.py`、`cli.py`、`latency.py` | SDK 演示 | 流式消费、首输出延迟、取消、输出预算 |
| 1-3 | `app.py` | FastAPI 内存运行与订阅演示 | 创建与订阅分离、事件重放、显式取消；重启不能恢复 |
| 1-4 | `helloPrompt.md`、`miniloop.md`、模板/校验片段 | Prompt 教学材料；`promptUnitest.py` 未装配完整测试依赖 | Prompt 约束、模板变量、不可信输入的角色边界 |
| 1-5 | `deepseek_structured_demo.py` | 本 fork 新增完整入口，含离线测试 | 原生 Schema、Pydantic、业务组合校验、有限纠错 |
| 1-5 | `fieldrule.py`、`validation.py`、`repair*.py`、`cache.py`、`all.py` 等 | 局部示例；部分可运行，部分引用未定义类型；`all.py` 也不是总启动入口 | 逐段理解类型、纠错与降级，再对照完整入口 |
| 1-6 | `gateway.py`、`test_gateway.py`、`test_gateway2.py` | 自有协议网关原型与脚本检查 | 白名单、主备、Trace；与 1-7 接口不同 |
| 1-7 | `llm-gateway/` | 完整 FastAPI 项目，已接入根检查 | 兼容 API、Schema 请求校验、路由、Prompt、用量持久化 |

1-2 的采样实验已改名为 [`sampling_demo.py`](../course_code/week01/1-2/sampling_demo.py)，清除原文件名前导不换行空格，Git 保留重命名关系。当前默认关闭思考，`top_p` 在供应商端固定为 1，其变化组不能用来证明参数效果。`temperature` 的随机性也不能由少量样本得出稳定规律。

### 运行早期 SDK 示例

以下命令在仓库根目录执行，路径写法适用于 macOS/Linux；Windows 的虚拟环境解释器位于 `Scripts/python.exe`。使用独立环境，避免把 OpenAI SDK 临时依赖混入 Gateway 锁文件：

```bash
uv venv work/python-demos --python 3.12
uv pip install --python work/python-demos/bin/python openai pydantic fastapi uvicorn httpx jsonschema jinja2
uv run --env-file .env --no-project --python work/python-demos/bin/python \
  python course_code/week01/1-2/chat.py
```

这个临时环境的 SDK 版本未锁定，只用于阅读实验；要得到可复现的教学环境，应记录安装版本后单独维护锁文件。不要把它的运行结果记成 Gateway 的锁定检查结果。

完整输出校验示例有锁定依赖入口，见 [DeepSeek 接入](deepseek.md)。Gateway 则按其 [README](../course_code/week01/1-7/llm-gateway/README.md)在模块目录启动，不需要先启动第三周 Agent。

## 第二周

| 章节 | 入口与材料 | 当前性质 | 建议关注点 |
| --- | --- | --- | --- |
| 2-1 | `minimal_tool_loop.py`、`model_select.py` | SDK 独立演示；其余工具定义多为片段 | 工具调用 ID、参数校验、宿主授权与结果回传 |
| 2-2 | `tool_runtime_demo_v2.py`、`test_tool_runtime_demo_v2.py` | 独立 Runtime 演示；离线测试已接入 | 定义/注册/快照/执行职责分离，旧快照仍受运行时停用控制 |
| 2-3 | `mcp_server_v1.py`、`mcp_client_v1.py`、`loop_v1.py`、`mcp_host_v1.py` | MCP 程序；SDK 直接依赖固定，stdio 单独联调，未接入根检查 | Client 拉起 Server、工具发现、名称投影、返回内容限制 |
| 2-4 | `tool_governance_v1.py`、`tool_governance_v2.py`、`tool_governance_demo.py` 与测试 | 治理的不同版本；离线测试已接入 | 对照每版实际能力，避免把 v2 描述成具备全部审批与超时功能 |
| 2-5 | 两个 `agent-tool-runtime-pi-v2` ZIP | 未展开的前后版本 | 在临时目录解压对照超时问题，不当作当前可直接启动项目 |

运行 2-2 的离线测试不需要 API Key：

```bash
make check-tools
```

运行模型驱动版本需要先导出根 `.env`，再从章节目录执行。例如使用 uv 显式读取根配置并使用该章 requirements：

```bash
uv run --env-file .env --no-project \
  --with-requirements course_code/week02/2-2/requirements.txt \
  python course_code/week02/2-2/tool_runtime_demo_v2.py
```

MCP 示例的 `mcp.Client` / `MCPServer` 接口使用 SDK v2；最小命令、固定版本和验证范围见 [2-3 README](../course_code/week02/2-3/README.md)。先运行无模型的 Client/Server，再接入模型 Loop；不要复用 Commerce 的 SDK v1 环境。

## 第三周

六个 Node 项目的安装、测试和编译由 `make install-agents`、`make check-agents` 管理。单项目可在根目录分别运行 `npm --prefix <目录> ci`、`npm --prefix <目录> test`、`npm --prefix <目录> run build`；真实 `start` 使用[统一 DeepSeek 配置](deepseek.md)。

| 项目 | 作用 | 首读文件 |
| --- | --- | --- |
| `3-1/codebase_agent_demo` | 第一版源码理解 Agent | `agent-runner.ts`、`runtime.ts`、`loop-guard.ts` |
| `3-1/codebasedemo` | 补齐模型、工具、Runtime 与循环测试的版本 | `tests/` 与对应 `src/` |
| `3-2/codebase_agent_demo` | 无计划修复对照组 | `completion-contract.ts`、`run-context.ts` |
| `3-2/planning_agent_demo` | 有依赖、证据与修订预算的计划组 | `plan-store.ts`、`plan-tools.ts`、`planning-prompt.ts` |
| `3-3/planning_agent_demo` | 增加任务状态、存档、审批和恢复 | `task-record.ts`、`checkpoint.ts`、`resume.ts` |
| `3-5/harness_agent` | 完整修复与交付实验 | `cli.ts`、`runtime.ts`、`test-process.ts`、`completion-contract.ts` |

早期项目的真实 `start` 会按自身上下文写 fixtures 或 artifacts，建议复制到临时目录再运行。离线测试使用受控模型；完整 Harness 创建独立工作区，适合先观察完整任务流程。fixtures 中有意保留的登录过期错误是修复任务输入，不是需要直接修复的项目缺陷。

3-2 的 `codebase.md`、`planning.md` 和 3-3 的交付说明保存当时的真实 Gateway 结果。轮数、模型和工具数量是历史实验数据，不是当前 Flash 的性能保证。

### Sandbox 与 Commerce

3-4 的 `pi-boundary-demo` 保存本地边界演示材料；`opensandbox-demo` 是 Docker 沙箱程序。它们需要宿主或容器服务配置，未被 Node 测试替代。Sandbox 的验收要观察被允许和被拒绝的文件、命令及网络操作。

3-5 的 Commerce 是独立全栈参考工程，包括共用核心、两种业务角色、三种运行路径和四种行业示例。先读[工程边界](engineering.md#commerce同一结果有两个消费者)，再选择本地 Messages 路径；DeepSeek 配置不会迁移 Anthropic 的托管平台。

## 改动前的核对方法

1. 确认所读文件属于哪个课堂版本，找到该版依赖与入口。
2. 对照实际请求、工具结果或状态转换，不仅看章节标题和注释。
3. 行为修改先用失败测试复现；资料整理逐项核对命令、路径、配置和输出。
4. 分别记录 Mock、真实模型、Web 与 Sandbox 的验收，不能互相替代。

课件 PDF 保留原内容，本轮没有逐页审阅；压缩包和历史运行材料也保留原实验背景。当前代码工程结果只覆盖[验证记录](verification.md)列出的范围。
