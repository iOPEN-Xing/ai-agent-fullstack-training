# 仓库协作约定

- 这是课程示例集合。保留 `course_code/weekXX/X-X/` 的章节结构、早期版本和教学产物。
- 阅读根目录 README、`docs/engineering.md` 和受影响模块的 README 后再修改。
- fixtures 的登录到期边界错误用于 Agent 验收。修复 Harness 时，通过其临时工作区验证该任务。
- 修改代码时保持原有语言与风格，注释优先使用中文，解释设计理由和边界。
- 行为修复用回归测试复现，按小批次验证和提交；依赖变更使用项目现有的锁文件。
- Gateway 用 `make check-gateway`；工具治理用 `make check-tools`；MCP 用 `make check-mcp`；Agent 用 `make check-agents`；Commerce 用 `make check-commerce`。文档与源码对应关系用 `make check-docs`，安装命令见 `CONTRIBUTING.md`。
- 统一离线检查为 `make check`。真实模型、Docker/Sandbox 和 Commerce Web 构建的范围见工程文档。
- 本地密钥仅放入被忽略的 `.env`，配置模板仅含占位值。运行存档和数据库不提交。
- Commerce 目录保留 Anthropic 的版权与 Apache-2.0 许可证；尊重其原有模块边界。
