# Codebase Agent：带分层测试的版本

在第一版上补齐模型接入、工具投影、Runtime 与 Loop Guard 的测试，用源码阅读任务观察完成证据。

## 安装与检查

在本目录执行，要求 Node.js 22.19.0+：

```bash
npm ci
npm test
npm run build
```

测试使用脚本化模型，不加载密钥文件。真实调用使用 `deepseek-flash` 官方 Chat 接口；在仓库根目录配置 `.env` 后执行本目录的 `npm start`。它会先读取根 `.env` 再读取本目录 `.env`，shell 变量优先。配置说明见 [DeepSeek 接入](../../../../docs/deepseek.md)。

真实入口按本版上下文操作 fixtures 与 artifacts，建议复制到临时目录实验。需要自动建立独立工作区的完整实验，使用 [3-5 Harness](../../3-5/harness_agent/README.md)。

## 代码阅读顺序

| 文件 | 看什么 |
| --- | --- |
| `src/model.ts` | 官方地址、鉴权来源、模型能力与输出预算 |
| `src/runtime.ts` | 允许的路径和动作，工具执行结果 |
| `src/pi-tools.ts` | Runtime 工具如何转换成 pi AgentTool |
| `src/loop-guard.ts` | 轮数、重复动作、完成条件与 Follow-up |
| `src/agent-runner.ts` | 上下文、工具结果和下一轮如何连接 |
| `tests/` | 各层接受和拒绝哪些行为 |

模型的最终文字不能替代完成证据。此版运行在宿主机，不提供容器或网络隔离；原始 fixtures 和课堂产物用于学习对照。
