# 当前验证记录

验证日期：2026-10-04。本机为 macOS，Node.js 24.14.0、Python 3.12.14、uv 0.12.22；CI 配置使用 Linux、Node.js 22.19.0 和 Python 3.12。以下数字是本轮结果，不是固定的课程用例数量。

## 离线检查

根 `make check` 运行 Gateway、工具、MCP Host、六个 Agent、Commerce、完整输出校验和文档源码对应检查。测试通过不表示课件中的每个片段都可运行。

| 范围 | 通过数 | 其他检查 |
| --- | ---: | --- |
| Gateway / 1-7 | 38 | 锁定依赖、Ruff |
| Tool Runtime / 2-2 | 3 | 离线工具执行 |
| MCP Host / 2-3 | 27 | 锁定依赖、真实 stdio、模型 HTTP Mock、Ruff |
| Tool Governance / 2-4 | 19 | 参数、权限、审计与执行错误 |
| 3-1 / codebase_agent_demo | 18 | TypeScript 编译 |
| 3-1 / codebasedemo | 39 | TypeScript 编译 |
| 3-2 / codebase_agent_demo | 18 | TypeScript 编译 |
| 3-2 / planning_agent_demo | 30 | TypeScript 编译 |
| 3-3 / planning_agent_demo | 45 | TypeScript 编译 |
| 3-5 / harness_agent | 71 | TypeScript 编译；新增真实挂起测试的预算回归 |
| Commerce Python | 1116 | 1 个原有条件跳过、Ruff、`scripts/check.py` |
| 完整 Structured Output | 5 | 三层校验、纠错上限、传输错误、Ruff |
| 文档源码对应检查器 | 9 | 重命名、注释/字符串伪声明、链接及测试失效 |
| 合计 | 1438 | 跳过用例不计入通过数 |

连接测试覆盖官方模型默认值、模型覆盖、密钥来源、URL 规范化与非法地址、显式关闭思考的实际请求和 SSE 解析。Commerce 新增四个行业的模型工厂、缺密钥、旧鉴权替换及不兼容配置回归。以上测试使用 Mock，不发送真实密钥。

本机 Commerce 的症状是 editable 包安装存在，但 `import commerce_common` 失败；`ls -lO <环境>/lib/python3.12/site-packages/*.pth` 显示 macOS hidden 标记，Python 因此忽略包路径。重新安装并不能解决反复隐藏的问题。本轮将相同固定依赖安装到工作区外的虚拟环境，再运行完整根检查：

```bash
make install-commerce COMMERCE_VENV=/tmp/ai-agent-commerce-20261004
make check COMMERCE_VENV=/tmp/ai-agent-commerce-20261004
```

`COMMERCE_VENV` 是 Make 新增的可选路径；默认仍为 Commerce 目录内 `.venv`，CI 使用这个默认路径；以上 hidden 标记问题是在本机 macOS 工作区观察到的。运行 API 时要使用实际安装环境的 Python；`/tmp` 路径只适用于临时验证，长期开发选用不会被工作区管理器隐藏的目录。

Harness 取消测试补充了三种权限错误场景：短暂 EPERM 等待回收、持续探测错误明确失败、拒绝信号且管道未关闭时在清理期限内失败。持续失败不会被当作进程已清理。

本轮另补单次测试的默认 30 秒预算；预算由宿主配置且进入验证指纹。MCP 覆盖空错误、多文本和非法结果、模型同轮多调用、白名单、本地参数拒绝、关联 ID、未知结果与取消传播。stdio 契约读取真实 Resource/Prompt；模型请求形态和多调用用 Mock 验证，真实接口结果另列。

Commerce 有两条依赖警告（Starlette TestClient 和 Pydantic Settings），未为了消除警告修改原有固定依赖。六个 Agent 的依赖版本与锁文件没有因模型接入而更新；之前生产依赖审计结果不能代表本次重新审计。

## 真实官方接口

`make check-live` 的九个检查使用当前账户、固定 `deepseek-flash`，每次设置有限输出预算，不启用重试。验收目标为 `api.deepseek.com`，脚本不使用 HTTP(S)_PROXY 环境变量。

| 检查 | 本轮结果 | 能说明什么 |
| --- | --- | --- |
| 模型列表 | HTTP 200，存在 Flash | 当前账户识别所用模型名 |
| Chat 普通输出 | HTTP 200 | 请求、鉴权与基本输出正常 |
| Chat JSON 模式 | HTTP 200，字段值正确 | JSON 语法与该简单结果正常 |
| Chat 原生 Schema 能力探测 | HTTP 400 | 错误体明确指向该格式类型当前不可用 |
| Responses Schema | HTTP 200、completed、本地结果正确 | 原生 Schema 的这一简单请求可用 |
| Tool Call、Tool Result 两轮 | 均 HTTP 200 | 调用 ID、参数和结果回传正常 |
| Chat SSE | 文本正确、有 `[DONE]` 和 usage | 基本流式消费与结束信号正常 |
| Anthropic Messages | HTTP 200 | SDK 所需基础兼容协议可用 |

完整输出校验示例也真实执行成功：缺资料的报销问题返回 `search_docs`，query 非空、answer 为 null，未纠错。它没有检索或执行工具。

1-7 Gateway 用 ASGI 客户端经过实际 Service、Router、HTTP Client 与临时 SQLite，调用官方上游：Chat、Responses Schema 和 Chat SSE 均成功。此联调未验证真实多供应商 fallback、并发、长流断连和容器部署。

## Agent 真实任务与离线恢复

完整 Harness 的真实命令为本目录 `npm start -- --workspace <临时目录> --run-id deepseek-20261004 --auto-approve`。自动批准仅用于这次临时 fixtures 实验，仍经过补丁暂存和摘要校验。

结果为 19 轮、`COMPLETED`、`completed`、代码版本 r1、六个计划步骤完成、三种测试范围通过，并写入 `artifacts/login-fix.md`。初始 target/boundary 失败、regression 通过；修改后各范围均 exit 0，证据对应当前内容。原 fixtures 没有改变。

`npm run lab:harness` 的固定动作实验另外完成了暂停、存档、历史回灌续跑、审批和交付核验。真实模型任务成功不代表真实模型的暂停/恢复实验也已执行；恢复的当前证据来自离线脚本和回归测试。

在本轮测试预算和控制流整理后，离线 `lab:harness` 再次完成，仍核对历史回灌、一次修改和三个测试范围。上述 19 轮真实模型修复来自前一轮接入验收，本轮没有再次发送同一 Harness 修复任务。

MCP 完整 Host 本轮使用 `mcp_host_v1.py --live` 联调，默认白名单只有 get_order。实际 3 轮：先取得 ord_missing 的明确 ORDER_NOT_FOUND，再查询 ord_1002 得到 shipped、1599 分，最后生成答案。运行前还通过固定成功、参数拒绝、远端错误三个契约检查；没有调用 create_ticket。

Commerce 零售 Shopping 与 Merchant 各跑了一轮官方模型请求，使用内存 Mock 后端；两者都出现 Tool Call、Tool Result、UI 和 `turn_complete`，未出现 error 事件。输入分别为只读商品推荐和业务快照；未验证变更审批、记忆提取、分析委派或其他三个行业的真实调用。

## 资料检查与人工复核

常用 Markdown 维护文档链接检查覆盖根 README、CONTRIBUTING、docs、周索引、六个 Agent README 和两版 Gateway README 以及 MCP 章节 README 的本地链接与章节锚点。新增三份深入链路文档与 code-map，当前 21 份文档、18 条对应关系、28 个关键符号。对应检查核对小节、定义和源码/测试链接，不验证所有 shell 代码块，也不自动证明业务语义一致；命令、环境优先级和状态语义仍需对照代码及实际运行。

前一轮文档用官方 `deepseek-flash` 分三批做文字与技术复核，前两批共 25 条建议、末批 8 条，意见再由源码和运行证据确认。本轮深入整理直接核对函数、控制流、状态、错误分支与测试，并以回归检查防止关键引用漂移；不把模型审核意见作为事实依据。历史课件、运行记录和 ZIP 不因当前默认模型变化而改写。

## 未覆盖的部分

- 八个 Commerce Web 应用未重新构建或进行浏览器验收；查看各行业 README 的入口。
- Docker、pi-sandbox、OpenSandbox 未启动；应用层检查不能替代隔离测试。
- Commerce SDK、Managed Agents 和定时托管部署未迁移或联调。
- MCP stdio、Resource/Prompt 契约和完整 Host 的官方模型查询已验收，依赖已锁定；HTTP 传输和工单变更仍未验收。较短 loop_v1 的请求由 Mock 检查，本轮未真实执行；早期 SDK 演示也未逐一运行。
- 课件 PDF 未逐页审阅，2-5 ZIP 未解压验收。
- GitHub Actions 是否通过需查看对应提交的远程运行，不能用本机结果代替。
