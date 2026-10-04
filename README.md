# AI Agent 全栈工程师训练营

这是按课程阶段组织的独立示例集合：第一周学习模型 API 和 Gateway，第二周把工具声明、授权与执行分开，第三周用计划、存档、审批和测试证据判断任务是否完成。它包含多个 Python/TypeScript 项目，各项目有自己的依赖和运行入口。

本 fork 保留课堂版本、fixtures 和历史运行材料，补充工程检查、中文代码注释和可运行示例。当前课程模型使用 `deepseek-flash`，六个 TypeScript Agent 默认直接调用 DeepSeek 官方 API。

## 先运行一条完整链路

建议环境为 Python 3.12、Node.js 22.19.0+、[uv](https://docs.astral.sh/uv/) 和 Make。在仓库根目录执行：

```bash
make install-agents
make install-commerce
make check
npm --prefix course_code/week03/3-5/harness_agent run lab:harness
```

`make check` 覆盖 Gateway、Tools、MCP Host、六个 Agent、Commerce、完整输出校验和文档源码对应检查，使用 HTTP Mock、真实本地 stdio 或固定模型动作，不需要密钥。早期片段、Web、Sandbox 与托管部署的范围见[验证记录](docs/verification.md)。`lab:harness` 在临时工作区里复现登录测试失败、修复、暂停、恢复和交付，不会修复原始 fixtures。正常报告应显示 `任务状态：completed` 与 `停止原因：COMPLETED`；进程 exit 0 也可能表示等待审批或暂停。

真实模型调用先配置根目录 `.env`：

```bash
cp .env.example .env
# 用编辑器填写 DEEPSEEK_API_KEY。
make check-live
npm --prefix course_code/week03/3-5/harness_agent start
```

`check-live` 会产生少量模型调用费用，检查官方接口的协议能力。`npm start` 开始真实修复任务，待审批补丁需要作出具体决定；运行输出会给出工作区和恢复命令。详细步骤见 [DeepSeek 接入](docs/deepseek.md)和 [Harness 指南](course_code/week03/3-5/harness_agent/README.md)。

## 阅读路线

| 文档 | 解决的问题 |
| --- | --- |
| [课程代码指南](docs/course-guide.md) | 每章看什么、哪个文件能运行、哪些文件需要结合课件阅读 |
| [工程结构与设计边界](docs/engineering.md) | 模型、工具、计划、状态和证据怎样协作，失败时由谁处理 |
| [结构化输出链路](docs/structured-output.md) | 原生 Schema、严格类型、业务组合和有限纠错对应哪些函数与测试 |
| [MCP Host 链路](docs/mcp-host.md) | 能力发现、授权、参数校验、多工具回传及未知结果怎样推进 |
| [Harness 生命周期](docs/harness-lifecycle.md) | 具体补丁审批、真实测试证据、完成判断和恢复核验怎样协作 |
| [DeepSeek 接入](docs/deepseek.md) | 配置从哪里来、使用哪种 API、如何判断兼容性 |
| [验证记录](docs/verification.md) | 检查覆盖了什么、真实运行结果是什么、哪些部分尚未验收 |
| [开发与远程同步](CONTRIBUTING.md) | 安装、修改、提交和同步上游 |

课件在 `course_materials/`，逐章代码在 `course_code/`，特定接口问题的历史复现在 `fqa/`。第一、二周包含课堂片段；目录里存在 `.py` 文件并不表示每个文件都能单独启动。

## 按周导航

- [Week 01](course_code/week01/README.md)：模型 API、流式输出、Prompt、输出校验、Gateway。
- [Week 02](course_code/week02/README.md)：Function Calling、Tool Runtime、MCP、工具治理。
- [Week 03](course_code/week03/README.md)：Codebase Agent、Planning、Checkpoint、Sandbox、Harness、Commerce。

Gateway 仍是独立教学服务。它的路由、用量和 Prompt 管理需要请求经过该服务才会生效；官方直连的 Agent 不会自动获得这些能力。
