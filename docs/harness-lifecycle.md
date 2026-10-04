# 从修复任务到可核验交付

对应第三周 [Harness 入口](../course_code/week03/3-5/harness_agent/README.md)。任务是修复登录会话到期边界，工作流必须拿到修改、测试、说明文档三类当前证据。模型提出动作，宿主根据实际文件和进程结果判定交付。

推荐先运行 `npm --prefix course_code/week03/3-5/harness_agent run lab:harness`。它使用固定动作模型，真实读取、修改和测试临时副本，并完成暂停/恢复；与真实模型共用 CLI、Runtime 和完成契约。

## 任务入口

[`cli.ts`](../course_code/week03/3-5/harness_agent/src/cli.ts) 的 `parseCliArgs` 区分新运行、resume、replay 及审批参数；`runCli` 决定创建独立工作区还是核查既有现场。新运行复制 fixtures，resume 保留原工作区，replay 用原任务和当前 fixtures 创建新现场，不复制旧证据。

[`lifecycle.test.ts`](../course_code/week03/3-5/harness_agent/tests/lifecycle.test.ts) 验证临时现场、CLI 参数、暂停与续跑、历史和审批。模型提示词无法替代这些入口选择。

[`run-context.ts`](../course_code/week03/3-5/harness_agent/src/run-context.ts) 的 `createExecutionContext` 提供宿主可信配置：目标源码、交付路径、三个测试范围、参与摘要的文件及测试超时。模型的 run_test 参数只有 scope，不能任意选择命令或把预算改成无限。

默认 `testTimeoutMs=30000`，只接受有效正整数毫秒数；[`test-budget.test.ts`](../course_code/week03/3-5/harness_agent/tests/test-budget.test.ts) 用真实挂起测试验证超时、失败证据及清理标记。慢测试可在宿主上下文调整预算，该预算也进入验证指纹，调整后需重新取证。

## 循环与计划

[`agent-runner.ts`](../course_code/week03/3-5/harness_agent/src/agent-runner.ts) 的 `runPlanningAgent` 组合模型、Runtime、计划、审批、记录和 Checkpoint；恢复时回灌原消息、计划、证据、任务计数与代码版本。它把各组件连接起来，业务判断留在各自模块，不在 Loop 内逐条硬编码测试通过条件。

[`plan-store.ts`](../course_code/week03/3-5/harness_agent/src/plan-store.ts) 中，`PlanStore` 管理依赖和步骤迁移，`EvidenceStore` 保存执行事实，`PlanningSession` 组合两者。pending 步骤只有依赖都完成后才可开始；in_progress 步骤满足其验证条件后才完成。修订先检查整个候选方案再提交，避免失败时留下半份计划。

[`TaskRecorder`](../course_code/week03/3-5/harness_agent/src/task-record.ts) 另外记录运行状态、步骤调用、计数和人工决定。它与 PlanStore 的步骤状态粒度不同；例如任务等待审批时，计划步骤仍可保持 in_progress，不需要发明一个计划状态来代替宿主决定。

对应测试是 [`agent-runner.test.ts`](../course_code/week03/3-5/harness_agent/tests/agent-runner.test.ts)、[`plan-store.test.ts`](../course_code/week03/3-5/harness_agent/tests/plan-store.test.ts) 和 [`lifecycle.test.ts`](../course_code/week03/3-5/harness_agent/tests/lifecycle.test.ts)。它们检查组合后的状态与依赖行为，模型是否选择高质量修复还需任务实验。

## 具体补丁审批

[`ApprovalGate`](../course_code/week03/3-5/harness_agent/src/approval.ts) 暂存的不是一句“允许修改源码”，而是 path/search/replace 与目标内容共同生成的 patchHash。Runtime 的 planPatch 只读取、计算，不写入；之后 `applyApprovedPatch` 在 [approval-flow.ts](../course_code/week03/3-5/harness_agent/src/approval-flow.ts) 检查批准内容，再调用 commitPatch。

批准后到实际写入前，目标文件和补丁摘要还要核对。文件发生变化就不能沿用旧批准；补丁已落盘但存档未完成时，也不能简单重复执行。`--auto-approve` 仍走这一条内容核验路径，只改变决定来源。

[`checkpoint-resume.test.ts`](../course_code/week03/3-5/harness_agent/tests/checkpoint-resume.test.ts) 与 [`lifecycle.test.ts`](../course_code/week03/3-5/harness_agent/tests/lifecycle.test.ts) 覆盖等待批准、恢复后批准、拒绝、过期内容和重复执行边界。原始 fixtures 的到期错误保留作为下一次任务输入。

## 测试证据

[`DemoToolRuntime`](../course_code/week03/3-5/harness_agent/src/runtime.ts) 是工具执行入口。其 runTest 工作流可按以下顺序核对：

1. scope 只能取 target、boundary、regression，文件和命令来自宿主上下文。
2. 标记 unfinishedTests，计算 beforeDigest。
3. 调用 [`executeTestProcess`](../course_code/week03/3-5/harness_agent/src/test-process.ts)，传入取消信号、30 秒默认预算及 4 MiB 输出上限。
4. 只有执行器确认清理后才清除未完成标记，再计算 afterDigest。
5. classifyTestResult 判读结果，形成模型可见信息及独立 Evidence。

摘要包含约定源码、三个范围的测试、配置/锁文件、Runtime 所在项目的包与配置输入、测试范围、测试预算和 Node 版本；约定目录递归展开后也参与摘要。它只能核验纳入的输入，不代表整个操作系统和所有外部服务已经固定。

| 优先级 | 执行事实 | resultCode | 能否作为通过证据 |
| --- | --- | --- | --- |
| 1 | 已取消 | ABORTED | 否 |
| 2 | 已超时 | TEST_TIMEOUT | 否 |
| 3 | 没有正常退出码 | TEST_RESULT_UNKNOWN | 否 |
| 4 | 前后输入摘要不同 | TEST_INPUT_CHANGED | 否 |
| 5 | 完整、稳定、exit=1 | OK，passed=false | 否；结果明确但测试失败 |
| 6 | 完整、稳定、exit=0 | OK，passed=true | 还需与交付时的当前内容匹配 |

工具 `ok=true` 表示得到完整可判读的结果；测试是否通过看 passed，不能只看 ok。执行或取证异常保留 TEST_RESULT_UNKNOWN，不伪造退出码。模型只看到输出末尾 30 行，Evidence 保存 scope/revision/command/files/exitCode/resultCode/前后摘要等结构化事实。

[`harness-evidence.test.ts`](../course_code/week03/3-5/harness_agent/tests/harness-evidence.test.ts) 检查旧结果、摘要与交付内容；[`test-budget.test.ts`](../course_code/week03/3-5/harness_agent/tests/test-budget.test.ts) 检查宿主预算；[`test-process.test.ts`](../course_code/week03/3-5/harness_agent/tests/test-process.test.ts) 检查真实进程、取消与清理失败。

POSIX 测试用独立进程组启动。取消/超时先 TERM，宽限期后 KILL，再等输出管道和进程组结束；持续 EPERM 或未关闭管道必须失败。30 秒是执行预算，清理还需要有限等待时间，因此工具不会精确在第 30 秒返回。Windows 没有同样的 POSIX 进程组语义；这套实现也不限制测试网络、磁盘或所有后代逃逸行为。

## 完成判断

[`createLoginFixContract`](../course_code/week03/3-5/harness_agent/src/completion-contract.ts) 定义交付条件，Runtime 的 captureCompletionState 在判断时重新读取文件。模型不能自报哈希来证明完成。

| 对象 | 必须满足的条件 |
| --- | --- |
| 计划 | 每个步骤为 completed 或 skipped |
| 修改 | 最近的有效 diff 对应目标路径和当前版本，修改前后不同，修改后哈希与当前源码一致 |
| 三种测试范围 | 每个范围取最近一次尝试；resultCode=OK、exit=0、passed=true、摘要稳定、版本和受测摘要匹配当前现场 |
| 交付说明 | 目标文件存在、非空，内容哈希匹配最后一次写入证据 |

“先通过、后超时”必须采用后一次失败，不能跳过失败寻找更早通过。“通过后又改源码/测试/预算”必须重跑。`r1` 是当前任务中的修改序号，不是 Git commit，也不能代替内容摘要。

缺项以字符串列表反馈给 Loop，模型再补齐动作。只有缺项为空并满足循环的结束条件，才能成为 COMPLETED。对应 [`harness-evidence.test.ts`](../course_code/week03/3-5/harness_agent/tests/harness-evidence.test.ts) 验证最近尝试优先、内容变化、伪造旧证据和交付文档变化。

## 暂停与恢复

[`checkpoint.ts`](../course_code/week03/3-5/harness_agent/src/checkpoint.ts) 的 `saveCheckpoint` 保存版本、校验和、任务、计划、证据、消息历史及工作区引用；写临时文件后 rename 替换目标，`loadCheckpoint` 检查格式、版本、校验和和序号。它提供单文件替换机制，没有跨进程写锁、数据库事务或断电持久性承诺。

[`resume.ts`](../course_code/week03/3-5/harness_agent/src/resume.ts) 先由 `inspectResumeState` 只读核查，再由 `prepareResume` 返回可续跑对象：

| 顺序 | 核查 | 不满足时 |
| --- | --- | --- |
| 1 | 存档格式、版本、完整性 | 拒绝加载 |
| 2 | 原工作区和目标 repo 仍存在 | 拒绝恢复，不重新复制 |
| 3 | 任务不是 completed/failed/cancelled 终态 | 终态需 replay 或新运行 |
| 4 | 工作区约定文件摘要 | 变化视为可能未存档写入，停止自动推进 |
| 5 | 引用的 journal 可读，未闭合操作数量合理 | 无法确认记录时拒绝 |
| 6 | 已启动调用有对应完整结果 | 结果不明不得自动重放写操作或宣称测试通过 |

Checkpoint 是业务快照，journal 是执行过程记录；两者分开是为了识别“动作可能已经发生，快照还没更新”。它们并未组成一笔原子事务，因此保守拒绝比无条件续跑更符合现有证据。

待审批信息随恢复对象还原；真正批准并执行时，仍由 ApprovalGate 与 Runtime 重新核对具体内容，恢复通过本身不等于批准补丁。

`--pause-after N` 在完整轮次和存档后暂停；它可能保留 running 状态，并不等于 cancelled。SIGINT 进入取消终态。恢复继续同一 run，保留消息和计数；replay 用新现场重新执行任务。不要用 exit 0 判断业务完成，报告还要检查任务状态、停止原因和完成契约。

[`checkpoint-resume.test.ts`](../course_code/week03/3-5/harness_agent/tests/checkpoint-resume.test.ts) 与 [`lifecycle.test.ts`](../course_code/week03/3-5/harness_agent/tests/lifecycle.test.ts) 对应存档损坏、现场缺失、结果不明、暂停续跑、审批和历史恢复。命令及审批参数见 [Harness README](../course_code/week03/3-5/harness_agent/README.md)。

## 定位失败与继续工程化

路径拒绝先看 Runtime 与上下文；补丁待批准看 ApprovalGate；测试挂起看 test-process 和时间预算；恢复拒绝看 inspection 中的 unresolved；无法完成看契约缺项。按失败所属层排查，避免把所有问题都归到提示词。

当前实现已覆盖课程任务的真实测试、内容证据、暂停恢复和具体补丁批准。要成为多人服务，还需要真实身份与权限、工作区锁、沙箱、外部副作用查询和可靠存储。这些能力应围绕明确业务需求增加，不能靠更多抽象类或更长提示词获得。各版本对照及当前验收边界见 [工程结构](engineering.md) 和 [验证记录](verification.md)。
