# Planning Agent

在 3-1 的 pi Loop 上增加计划层，任务是修复登录会话到期判断。计划规定依赖和验收证据，Runtime 执行文件操作与测试，完成契约决定何时交付。

## 安装与运行

在本目录执行：

```bash
npm ci
npm test
npm run build
# 根目录 .env 配置完成后才执行真实调用。
npm start
```

真实调用默认直连 `deepseek-flash`，读取根 `.env` 和本目录 `.env`，shell 变量优先；见 [DeepSeek 接入](../../../../docs/deepseek.md)。此版真实入口会操作自己的 fixtures 和 artifacts，建议在临时副本里观察修复；[3-5 Harness](../../3-5/harness_agent/README.md)会自动创建独立工作区。

## 计划与执行

| 模块 | 职责 |
| --- | --- |
| `plan-store.ts` | 步骤依赖、证据归属、状态、修订预算和原子修订 |
| `plan-tools.ts` | 创建、查询、更新和修订计划的模型接口 |
| `planning-prompt.ts` | 注入当前计划快照与行为要求 |
| `runtime.ts`、`run-context.ts` | 路径、读写、补丁、测试范围和执行证据 |
| `completion-contract.ts` | 检查计划、有效修改、测试和交付物 |
| `agent-runner.ts`、`loop-guard.ts` | 编排循环、拦截提前完成并反馈缺项 |

有计划后，写文件、补丁和测试需要带 `planStepId`。依赖尚未完成时不能启动下游步骤；步骤完成需要符合验收要求的本步骤证据。`revise_plan` 保留旧步骤并改接下游依赖，验证失败时原计划不变。

## 案例边界

原 fixtures 只按 UTC 日期判断过期，无法表达“到期时刻即失效”。固定时钟测试可稳定复现，修复应只修改 `session-policy.ts` 并保留公共 API；不要直接提交修复后的 fixtures，因为它是后续 Agent 实验的输入。

这一版的版本标识和测试证据用于教学；3-5 进一步把测试证据绑定到源码、测试和配置的内容摘要，不能把两版的校验强度视为相同。`artifacts/login-fix.md` 等文件是历史实验产物，当前模型的结果需重新运行观察。
