# 开发与远程同步

## 准备环境

Node 的建议版本见 `.nvmrc`，Python 的建议版本见 `.python-version`。安装 uv 后，在仓库根目录执行：

```bash
make install-agents
make install-commerce
make check
```

Gateway 检查会自动从 `uv.lock` 安装开发依赖。第二周工具示例通过 uv 的独立环境运行，Commerce 使用自己的 `.venv`，避免各项目的 pytest 版本相互影响。所有 Make 命令应在根目录运行；单个 Node 项目可使用 `npm --prefix <项目目录> test` 和 `npm --prefix <项目目录> run build`。

`.env`、`gateway.yaml`、数据库、依赖目录和运行存档已加入忽略规则。需要新增配置项时，更新对应的 `.env.example`，只填写占位值。课堂保留的 `artifacts/` 和 fixtures 属于学习材料；运行产物优先写入临时工作区。

## 修改与验证

1. 保留按周和小节排列的目录结构，先确认当前文件属于哪一版课堂示例。
2. 行为修复先写能复现问题的测试，再实施修改。fixtures 中的登录边界错误是 Agent 修复任务的输入。
3. 注释解释职责、设计理由、失败语义和信任边界；避免逐行翻译显然的语句。
4. 运行受影响模块的检查；修改公共入口或依赖文件时运行 `make check`。
5. 提交前执行 `git diff --check`，检查暂存内容中是否混入本机配置。

Commerce 来源于 Anthropic 的参考实现，其许可证和版权声明保留在对应目录。新增或修改相关文件时遵守该目录的 Apache-2.0 许可。仓库根目录当前没有统一许可证，分发课程材料前应确认相应授权。

## 分支与推送

```bash
git switch -c engineering/<变更名称>
git add <本次变更的文件>
git diff --cached
git commit -m "fix(module): describe the behavior change"
git push -u origin HEAD
```

`origin` 指向自己的 fork。当前工程改动分支为 `engineering/annotate-and-validate`，可通过 GitHub Compare 审阅，再合并到 fork 的 `main`。

## 同步课程上游

首次添加上游：

```bash
git remote add upstream https://github.com/Blackoutta/ai-agent-fullstack-training.git
```

若已存在 `upstream`，先用 `git remote -v` 确认地址。工作区干净后同步：

```bash
git fetch upstream
git switch main
git merge upstream/main
make check
git push origin main
```

遇到冲突时按课程版本核对，再验证和提交。CI 在 push、pull request 和手动触发时执行离线检查；fork 仓库如尚未启用 Actions，需要在 GitHub 的 Actions 页面启用。
