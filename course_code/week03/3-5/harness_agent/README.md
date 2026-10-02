# Agent Harness Demo

第三周 3-5 的完整示例：在 Planning Agent 上接入状态机、业务 Checkpoint、补丁审批、真实测试进程和内容绑定证据，以修复登录会话到期边界为任务完成修改与交付。

## 离线运行

要求 Node.js 22.19.0+。在本目录执行：

```bash
npm ci
npm test
npm run build
npm run lab:harness
```

`lab:harness` 使用脚本化模型，在新临时工作区中运行同一套 CLI 与 Loop。它先复现 fixtures 的失败测试，在第六轮暂停并保存存档，再回灌会话历史续跑，审批补丁、执行三种测试范围并生成 `artifacts/login-fix.md`。脚本最后核对恢复方式、历史保留、代码仅修改一次和完成契约。

fixtures 的到期判断错误是实验输入。实验在临时工作区中修复它，课堂原始文件保留供下次复现。

## 接入第一周 Gateway

先按 [1-7 Gateway README](../../../week01/1-7/llm-gateway/README.md) 启动服务，并在 `gateway.yaml` 中为 `smart` 配置可用的供应商路由。

在本目录配置调用方环境：

```bash
cp .env.example .env
# 编辑 .env，使 GATEWAY_API_KEY 与网关配置一致。
set -a; source .env; set +a
npm start
```

| 变量 | 默认值 | 含义 |
| --- | --- | --- |
| `GATEWAY_BASE_URL` | `http://127.0.0.1:8000/v1` | Gateway 兼容 API 地址 |
| `GATEWAY_API_KEY` | 无 | 调用方网关密钥 |
| `GATEWAY_MODEL` | `agent-default` | 网关公开模型别名；模板使用 `smart` |

环境变量在模型模块加载时读取，修改后重新启动进程。默认 `agent-default` 兼容先前课程配置；1-7 的示例公开 `smart`、`fast` 等别名，通过 `GATEWAY_MODEL` 选择。

## 暂停、审批与恢复

```bash
# 指定工作区，在完整轮次和存档结束后暂停。
npm start -- --workspace /tmp/my-harness-lab --run-id run-demo --pause-after 6

# 核验现场并续跑；有待审批动作时会展示具体补丁。
npm start -- --workspace /tmp/my-harness-lab --resume run-demo

# 对待审批动作作出人工决定。
npm start -- --workspace /tmp/my-harness-lab --resume run-demo --approve

# 在独立工作区重跑原任务。
npm start -- --workspace /tmp/my-harness-lab --replay run-demo
```

存档位于 `<workspace>/.agent-runs/<runId>.json`。优雅暂停保留可恢复状态；SIGINT 会进入取消终态。真实模型的 `npm run lab:cycle` 会执行暂停与恢复实验；它会调用已配置的 Gateway。

## 模块职责与边界

| 文件 | 职责 |
| --- | --- |
| `cli.ts`、`run-context.ts` | 参数、工作区、运行/恢复/重跑入口 |
| `agent-runner.ts`、`loop-guard.ts` | Loop 编排、轮数与重复动作保护 |
| `plan-store.ts`、`completion-contract.ts` | 计划依赖、证据和完成条件 |
| `runtime.ts`、`test-process.ts` | 工具执行、源码摘要、真实测试、取消与超时 |
| `checkpoint.ts`、`resume.ts` | 原子存档、校验与恢复现场检查 |
| `approval.ts`、`approval-flow.ts` | 补丁暂存与批准内容哈希核验 |

本示例的测试进程运行在宿主机，POSIX 平台通过进程组终止清理子进程。路径校验、补丁审批和 Loop Guard 提供应用层控制；生产执行还需配合 Sandbox。课程分层与验证范围见[根目录工程文档](../../../../docs/engineering.md)。
