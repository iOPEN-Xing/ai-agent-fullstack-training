# Agent Harness

本章在 Planning 与 State 示例上，增加内容绑定证据、真实测试进程和取消传播。任务是修复登录会话到期边界，并让目标、边界、回归三个范围的测试及交付说明对应当前代码。

入口、补丁审批、测试结果判读、完成契约与恢复的逐模块阅读见 [Harness 生命周期](../../../../docs/harness-lifecycle.md)。

## 先运行离线实验

在本目录执行，要求 Node.js 22.19.0+：

```bash
npm ci
npm test
npm run build
npm run lab:harness
```

`lab:harness` 使用固定动作模型，在新临时工作区复制 fixtures，复现失败、暂停并存档、回灌历史续跑、审批补丁、执行真实测试和生成 `artifacts/login-fix.md`。它核对恢复方式、历史保留、代码只修改一次和完成契约，不需要密钥。

fixtures 的错误是任务输入；实验修复副本，原文件继续用于下一次复现。脚本打印实际工作区，不要把其存档混入课程源码。

## 官方 DeepSeek 运行

在训练营仓库根配置 `.env`，然后回本目录执行 `npm start`：

```bash
# 本目录执行；具体配置和小额接口检查见根 docs/deepseek.md。
npm start
```

| 变量 | 默认值 | 含义 |
| --- | --- | --- |
| `DEEPSEEK_API_KEY` | 无 | 官方 API 密钥，没有本地 Gateway 密钥回退 |
| `DEEPSEEK_MODEL` | `deepseek-flash` | 官方模型 ID |
| `DEEPSEEK_BASE_URL` | `https://api.deepseek.com/v1` | 只允许官方根路径或 `/v1` |

加载优先级为 shell、本目录 `.env`、训练营根 `.env`。环境变量在模块加载时读取，修改后重启。`lab:cycle` 也读取这些配置，执行真实模型的暂停/恢复实验；离线 `test` 和 `lab:harness` 不读取密钥文件。[接入与协议边界](../../../../docs/deepseek.md)。

本版不经过第一周 Gateway。网关的路由、用量和 Prompt 管理要通过它自己的客户端入口观察，见 [Gateway README](../../../week01/1-7/llm-gateway/README.md)。

## 暂停、审批、恢复和重跑

```bash
# 第 6 个完整轮次和存档后暂停；不自动批准补丁。
npm start -- --workspace /tmp/my-harness-lab --run-id run-demo --pause-after 6

# 核验原现场；待审批时输出具体补丁和决定入口。
npm start -- --workspace /tmp/my-harness-lab --resume run-demo

# 仅对存档里的具体待审批补丁作出决定。
npm start -- --workspace /tmp/my-harness-lab --resume run-demo --approve

# 从原任务和当前课堂 fixtures 建立独立工作区。
npm start -- --workspace /tmp/my-harness-lab --replay run-demo
```

模型动作有变化，六轮时不一定恰好已经提出补丁。先执行不带决定的 `--resume`：若显示 `waiting_approval` 与具体补丁摘要，再加 `--approve` 或 `--reject`；若没有待审批动作，不要添加决定参数。`--reject` 拒绝该补丁；`--auto-approve` 用于明确允许自动修改临时 fixtures 的实验，仍走暂存与摘要核验。

存档位于 `<workspace>/.agent-runs/<runId>.json`。`--pause-after` 是可恢复暂停；SIGINT 进入取消终态。恢复前检查存档、执行记录、任务状态和工作区摘要，结果不明的写操作不会自动重放；目标 repo 缺失时拒绝恢复，不会重新复制并假装回到原现场。终态需 replay 或新运行，不能 resume。

## 怎样判断成功

报告必须显示 `任务状态：completed`、`停止原因：COMPLETED` 和完成契约满足。进程 exit 0 也可能表示等待审批或暂停，不能只看退出码。

目标源码要匹配有效修改证据；每个测试范围取最近一次尝试，要求真实 exit 0、前后输入摘要相同且与当前源码/测试/配置一致。测试通过后又改文件，或者随后取消/超时，旧通过不能用于交付。交付文档还要存在、非空、内容匹配最后写入证据。

每次 `run_test` 默认有 30 秒墙钟预算，输出上限为 4 MiB。预算来自 `createExecutionContext({ testTimeoutMs })`，不由模型的工具参数决定；它也参与验证指纹。需要较慢测试时在宿主上下文调整，并重新取得测试证据。模型轮数上限不能替代测试进程的时间上限。

## 阅读模块

| 文件 | 责任 |
| --- | --- |
| `cli.ts`、`run-context.ts` | 参数、工作区、运行/恢复/重跑入口 |
| `agent-runner.ts`、`loop-guard.ts` | 循环、轮数与重复动作保护、Follow-up |
| `plan-store.ts`、`completion-contract.ts` | 依赖、步骤证据、完成缺项 |
| `runtime.ts`、`test-process.ts` | 工具、内容摘要、真实退出码、超时与取消 |
| `checkpoint.ts`、`journal.ts`、`resume.ts` | 存档、执行记录与恢复现场检查 |
| `approval.ts`、`approval-flow.ts` | 补丁暂存和批准内容核验 |

测试进程在宿主运行，POSIX 使用进程组终止子进程；这不是容器隔离。路径与补丁限制、Loop Guard、内容摘要只覆盖本示例约定范围。需要服务化时继续验证符号链接、权限、网络、资源和并发写入。当前实测结果见[验证记录](../../../../docs/verification.md)。
