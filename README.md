# Design Agent MVP

上传一张设计稿图片和一份 PRD，由后台 Agent 在固定的客户管理项目中创建任务分支、规划改动、编写代码、运行 TypeScript 检查和构建，交付代码差异与应用预览。

这个版本面向单人本地演示：React + TypeScript + Vite 前端，FastAPI 后端，LangGraph 流程编排，LangChain 模型与工具调用，SQLite 任务状态，Git worktree 隔离开发。设计稿识图、开发计划和编码默认使用 `glm-5.3-flash`。暂未加入 RAG。

## 目录

| 路径 | 内容 |
| --- | --- |
| `design-agent/` | 上传工作台、后台任务、模型适配、代码生成与测试 |
| `customer-manager/` | 青禾 CRM 基线应用：客户列表、详情、新增、编辑、分页和本地持久化 |
| `mock/prd/` | 按版本编号的模拟需求文档 |
| `mock/ui/` | 对应的模拟设计稿与提示词 |
| `design-agent-ui/` | Agent 工作台 UI 设计稿及参考原型 |
| `scripts/` | 本地 CRM 仓库初始化脚本 |

## 本地启动

需要 Git、Node.js 22.12+、Python 3.12 和 uv。

```sh
git clone https://github.com/BruceZM/design-agent-mvp.git
cd design-agent-mvp
cp design-agent/.env.example design-agent/.env
# 编辑 design-agent/.env，填写自己的 LLM_API_KEY。
./启动MVP.sh
```

打开：

- Design Agent：<http://127.0.0.1:8011>
- CRM 基线：<http://127.0.0.1:5174>

启动脚本会安装锁定的依赖并构建前端。首次从远程克隆时，它会在 `customer-manager/` 初始化独立的本地 Git 仓库，供 Agent 创建 worktree；如果该目录已有 Git 仓库，则保留现有分支和历史。模型密钥只放在本地 `.env`，不会进入 Git。

在 VS Code 中打开 `design-agent-mvp.code-workspace` 可同时查看整个项目、Agent 和 CRM。`main` 保留 CRM 基线；已完成需求的代码位于 `design-agent/t-*` 分支，可在 GitHub Compare 中和 `main` 比较。详见 [任务分支说明](docs/任务分支说明.md)。

## 尝试一个需求

在工作台上传 `mock/ui/feature-ui-1.png` 和 `mock/prd/feature-prd-1.md`。需求是给客户列表增加关键词搜索。提交后会启动真实模型任务，消耗你配置的模型额度。关闭网页后任务继续在后台运行，停止后端会中断正在执行的任务。

## 验证

```sh
cd design-agent
uv sync --locked
uv run pytest -q
cd frontend
npm ci
npm run build
cd ../../customer-manager
npm ci
npm run typecheck
npm run build
```

Agent 自动检查只包含 TypeScript 和构建；浏览器功能与视觉验收另行记录，编译通过不能代表设计稿还原或交互验收通过。现有记录：[初版验收](design-agent/docs/验收记录.md)、[多模态识图升级验收](design-agent/docs/多模态识图升级验收.md)。其中的任务链接与运行截图路径来自原本地演示，远程克隆不包含历史任务数据库和上传记录。

更多说明：[Agent 使用说明](design-agent/README.md)、[CRM 开发规则](customer-manager/README.md)、[产品与原型](customer-manager/docs/产品与原型.md)、[模拟材料](mock/README.md)、[前端方案](Design-to-Code-MVP前端方案.md)。

服务仅绑定 `127.0.0.1`，没有登录和操作系统沙箱，也不自动推送或合并生成的任务代码。适合在可信本地环境演示。
