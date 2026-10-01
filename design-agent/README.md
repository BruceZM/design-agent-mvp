# Design Agent · 固定仓库 MVP

网页上传一张 UI 图片和一份 PRD，后台通过 LangGraph 执行材料解析、Git worktree 准备、开发计划、LangChain 编码工具调用、检查与一次有限修复，交付本地分支、代码差异、报告和可打开的构建预览。

目标固定为相邻的 `../customer-manager` 仓库，基线固定为 `main`。页面不提供仓库 URL 输入。没有 RAG、登录、远程推送或部署。

## 学习入口

后台 Agent 的调用顺序见 [代码阅读指南](docs/代码阅读指南.md)：`main.submit` → `Worker.loop` → `Workflow.run` → 六个执行节点 → `Developer` 模型工具循环。可对照 [项目流程图](../docs/项目流程图.md) 阅读函数内的中文注释。

## 启动

需要 Node.js 22.12+、Python 3.12 和 uv、Git。图片解析使用远程多模态模型，不再依赖 macOS OCR、Swift 或 Xcode。依赖版本记录在 npm lock 与 `uv.lock`。

```sh
# 在 design-agent 目录
uv sync --locked
cd frontend
npm ci
npm run build
cd ..
uv run uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8011
```

打开 http://127.0.0.1:8011 即可使用构建后的网页。开发前端时另开终端运行 `cd frontend && npm run dev`，地址 http://127.0.0.1:5175 ，API 代理到 8011。

客户基线：在 `../customer-manager` 执行 `npm ci && npm run dev`，地址 http://127.0.0.1:5174 。也可从项目父目录执行 `./启动MVP.sh`，按脚本输出打开地址。

首次从统一公开仓库克隆时，先在项目根目录执行 `./scripts/init-local-crm.sh`，为 CRM 初始化独立的本地 Git 基线。`./启动MVP.sh` 会自动执行这一步；已有 CRM 仓库的分支和历史保持不变。

## 模型配置

复制 `.env.example` 为 `.env`，只在本地填写密钥。本次配置读取了用户指定的凭据文件，写入 Git 忽略的 `.env`，权限为 0600。前端不会收到密钥。

- 编码：通过 LangChain 的 OpenAI 兼容客户端接入 GLM Coding Plan，默认 `glm-5.3-flash`。这是客户端适配层，并不代表使用 OpenAI 模型。
- 图片解析：默认 `VISION_MODE=remote`，使用同一个 `glm-5.3-flash` 模型，向 `VISION_BASE_URL` 提交原图并提取布局、组件、颜色及可见文字。已使用当前密钥和 Coding Plan 入口实际验证 mock 图的图片输入。模型能够识图，不代表生成代码已自动完成浏览器或视觉验收。
- 思考模式：GLM-5.3-Flash 只支持启用思考，使用 `reasoning_effort=low` 控制 MVP 延迟，并在连续工具调用之间保留 `reasoning_content`。旧 GLM 模型仍保留原来的参数配置。
- 原来的本机 OCR 实现已替换；旧任务的 OCR 解析记录继续保留，便于查看历史结果。
- 编码与视觉 SDK 均不自动重试；每个任务最多 16 次编码/计划模型调用、最多 1 轮检查修复，另有 1 次视觉请求，外层 110 秒超时。识图失败会停止任务并保留错误，不自动重试或回退 OCR。
- 任务时间预算在模型调用前检查，单次编码请求 90 秒，单次构建检查 100 秒。这些是本地过程限制，不是容器级硬隔离。

支持设计稿 PNG/JPEG/WebP ≤5 MB，PRD UTF-8 Markdown/TXT、DOCX、文字型 PDF ≤20 MB、提取文字 ≤50,000 字符。扫描/加密 PDF 暂不支持；错误在创建任务前返回。

## 使用示例

上传 `examples/sample-design.png` 和 `examples/sample-prd.md`，提交「客户列表状态筛选」需求。图片是基线视觉参考，筛选要求由 PRD 明确。任务详情支持刷新恢复、分阶段日志、分支复制、代码差异、报告下载和预览。

`succeeded` 表示产生了源文件修改，且 TypeScript 与构建通过；浏览器功能和 UI 视觉验收单独记录，不能由编译结果推断。每个任务在 `runtime/tasks/<id>/` 保存原材料、视觉规范、计划、日志和报告。worktree 在 `runtime/worktrees/<id>/`。

## 任务与数据边界

- SQLite 保存快照、单调递增 revision、事件 seq。一个后台线程串行取队列；关闭网页不停止任务。
- 服务停止会打断进程中的长任务。重启时将执行中任务标记中断，保留已有分支；排队任务继续处理。此版本不自动从 LangGraph 节点恢复。
- 同一提交标识和同一材料只创建一个任务；同一标识换材料返回冲突。提交响应丢失后可查询提交标识，重试沿用原标识。
- 模型只可读 README 和 src，只可写 src 的 TS/TSX/CSS；没有任意 shell、远程 Git 或密钥读取工具。检查命令由后端固定。
- 面向单人本地演示，服务仅绑定 127.0.0.1。路径校验和 worktree 不等于操作系统沙箱；生成代码的运行也必须限定在可信本地演示范围。

## 验证与结构

```sh
uv run pytest -q
cd frontend && npm run build
```

`tests/` 的假视觉/假模型只用于离线回归，不提供给网页或运行时，也不算真实模型成功。初版真实任务和浏览器验收见 [初版记录](docs/验收记录.md)；当前模型及识图流程的验证见 [多模态升级记录](docs/多模态识图升级验收.md)。

后端：`documents.py` 文件解析；`repository.py` 固定 Git/工具边界；`models.py` GLM 参数与思考内容适配；`agent.py` LangChain 计划和编码；`workflow.py` LangGraph 状态机；`store.py` SQLite；`worker.py` 串行执行；`main.py` 上传、状态、交付与预览 API。前端：React + TypeScript + Vite，两个路由 `/` 与 `/tasks/:id`。

参考：[LangChain Agents](https://docs.langchain.com/oss/python/langchain/agents)、[LangGraph 工作流](https://docs.langchain.com/oss/python/langgraph/workflows-agents)、[GLM-5.3-Flash](https://docs.z.ai/guides/vlm/glm-5.3-flash)。
