# State、Checkpoint 与人工审批

本版在 Planning Agent 上增加业务状态、执行记录、存档和恢复。要解决的问题是：进程中断后，哪些动作已完成，哪些未开始，哪些结果不明；能够继续对话并不表示能够安全继续写文件。

## 安装和模型配置

在本目录执行：

```bash
npm ci
npm test
npm run build
```

`npm start` 默认使用官方 `deepseek-flash`，读取训练营根 `.env` 与本目录 `.env`，shell 变量优先。[统一配置](../../../../docs/deepseek.md)。离线测试使用脚本化模型。

## 可复现的离线暂停与恢复

```bash
LAB_WORKSPACE=$(mktemp -d)
node --import tsx scripts/child-run.ts --scenario ac_full \
  --workspace "$LAB_WORKSPACE" --run-id state-lab --pause-after 6 --auto-approve
node --import tsx scripts/child-run.ts --scenario ac_full \
  --workspace "$LAB_WORKSPACE" --resume state-lab --auto-approve
```

两次调用使用同一工作区。第一个进程在完整轮次和存档结束后暂停；第二个先核验现场，再沿原会话、轮数、计划与证据继续。`--auto-approve` 用于临时 fixtures 的固定实验，仍检查具体补丁摘要；人工审批模式不传此参数。

真实模型的 `npm run lab:cycle` 使用同一 CLI，自动新建工作区并执行暂停/恢复。模型动作和轮数会变化，脚本成功与否要看其验收输出。

## 入口参数

| 参数 | 语义 |
| --- | --- |
| `--workspace <dir>`、`--run-id <id>` | 指定新运行现场与 ID |
| `--pause-after N` | 第 N 个完整轮次和存档后暂停，可续跑 |
| `--resume <id>` | 检查原现场后继续；终态运行不能续跑 |
| `--approve` / `--reject` | 对恢复记录中的具体待审批补丁作出决定 |
| `--auto-approve` | 临时实验自动决定，仍检查补丁与当前文件摘要 |
| `--replay <id>` | 用原任务与当前课堂 fixtures 建立独立工作区 |
| `--crash-point <name>` | 固定实验的异常退出点，不能当作优雅暂停 |

人工流程示例：运行 `npm start -- --workspace <dir> --run-id <id>`；等待审批后，先用 `--resume <id>`查看待决定内容，再加 `--approve` 或 `--reject`。没有决定时不会启动模型。进程退出码 0 也可能表示等待决定或优雅暂停，需看任务状态。

`completed`、`failed`、`cancelled` 是终态；其他状态仍需继续或人工处理。不要以同一未终结 run ID 再启动新运行；使用 resume。终态同名存档可能被新运行覆盖，保留原实验时用 replay 或新的 ID。

## 恢复检查与审批绑定

| 文件 | 责任 |
| --- | --- |
| `task-record.ts` | 状态迁移、步骤尝试与执行记录 |
| `checkpoint.ts` | 信封格式、序号、校验和、临时文件 rename 写入 |
| `journal.ts` | pi 的 JSONL 执行记录 |
| `resume.ts` | 存档、工作区、状态和上次动作三态核验 |
| `approval.ts`、`approval-flow.ts` | 具体补丁暂存、摘要核验、批准后的执行 |
| `fresh-run.ts` | 独立重跑，原记录只读 |

上次动作有完成记录即已完成，没有启动记录即未开始，只有启动记录或现场与存档不符即结果不明。结果不明的写操作不会自动重放。补丁参数或目标文件改变会使旧批准失效；模型没有批准自己的工具入口。

存档在 `<workspace>/.agent-runs/<runId>.json`，写入方式是临时文件后 rename。当前版本使用低层 journal 和 `runAgentLoopContinue`；已安装 pi 的 `AgentHarness.resume()` 尚是未实现入口，不能据名字直接使用。

本版运行于宿主机，存档并不等于数据库事务或操作系统隔离。3-5 在此基础上加强内容绑定证据、真实测试取消和现场核验，见 [Harness 指南](../../3-5/harness_agent/README.md)。
