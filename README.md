# AI Agent 全栈工程师训练营课程代码

本仓库是一组按课程阶段组织的独立示例，包含 Python Gateway、Tool Runtime、TypeScript Agent 与 Commerce 全栈参考项目。各示例使用自己的依赖文件和运行入口。

## 本 fork 的工程入口

- [项目分析与代码阅读路线](./docs/engineering.md)：目录职责、调用链、已修复问题与验证范围。
- [开发与远程同步说明](./CONTRIBUTING.md)：环境准备、检查命令、提交和上游同步。
- [最终 Harness 运行指南](./course_code/week03/3-5/harness_agent/README.md)：离线实验与 Gateway 联调。

建议使用 Node.js 22.19.0+、Python 3.12、uv 和 Make。安装依赖后可在根目录统一检查：

```bash
make install-agents
make install-commerce
make check
```

检查使用测试模型或 HTTP Mock，不需要模型 API Key。Gateway 使用 `uv.lock`，Agent 使用 `package-lock.json`，Commerce 使用已有的固定版本依赖；第二周示例沿用各自的 requirements 版本范围。`make help` 可查看单模块命令。Commerce 的八个 Web 应用、Docker/Sandbox 和真实模型调用的验收入口见[验证范围](./docs/engineering.md#验证范围)。

## Navigation

- [Week 01](./course_code/week01/)：从 Agent 全栈工程师能力与首个 Loop 出发，系统学习模型 API、Streaming、Prompt Engineering、Structured Output，并完成可治理的 LLM Gateway。
- [Week 02](./course_code/week02/)：从 Function Calling 与 Tool Use 出发，逐步完成工具协议与安全执行、MCP 接入、Runtime 治理，以及可审计的 Agent 工具基础设施。
- [Week 03](./course_code/week03/)：将 Tool Runtime 接入 pi Agent Loop，实现最大轮数、重复动作与完成条件等循环保护，叠加 Planning 计划层与证据校验；再补齐任务状态机、Checkpoint 与人工审批恢复，划定 pi-sandbox 与 OpenSandbox 执行边界，最终用 Agent Harness 把准备、修改、验证、异常处理、恢复与交付串成完整闭环，并对照 Anthropic commerce-agents 的手写 Loop。
