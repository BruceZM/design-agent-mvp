# 本地 Design Agent MVP 交付

三个阶段已完成：客户应用的原型/UI/实现，固定仓库的 LangChain/LangGraph 后台，离线回归和真实模型开发的浏览器验收。

## 直接打开

- [Design Agent 工作台](http://127.0.0.1:8011)：上传设计稿与 PRD，创建后台开发任务。
- [客户管理基线](http://127.0.0.1:5174)：main 分支，没有筛选功能。
- [真实任务结果](http://127.0.0.1:8011/tasks/t-c4764bfc713f)：阶段日志、代码差异、报告、预览。
- [Agent 开发的筛选版本](http://127.0.0.1:8011/api/tasks/t-c4764bfc713f/preview/)：状态筛选、重置、分页联动。

本次服务已启动。如果地址无法访问，在本目录终端运行 `./启动MVP.sh`，保持终端运行；Ctrl+C 只停止该脚本新启动的服务。网页关闭不会取消后台任务，后台服务停止会中断执行中的任务。

## 文件导航

- [客户应用说明](customer-manager/README.md)、[交互原型](customer-manager/docs/prototype.html)、[列表 UI 稿](customer-manager/docs/ui/01-list-design.png)、[编辑 UI 稿](customer-manager/docs/ui/02-edit-design.png)。UI 稿使用内置 imagegen，提示词同目录，不能确认具体模型版本。
- [Agent 配置和运行说明](design-agent/README.md)、[实现方案](design-agent/docs/方案与边界.md)、[初版验收记录](design-agent/docs/验收记录.md)、[多模态升级验收](design-agent/docs/多模态识图升级验收.md)。
- `design-agent/examples/sample-design.png` 与 `sample-prd.md` 可用于查看本次输入。重新提交会创建新的真实模型任务并消耗配置的模型额度。

初版筛选任务由真实 `glm-4.7` 编码工具调用生成，改动 2 个源文件，13 次计划/编码调用，typecheck/build 通过。初版额外浏览器检查覆盖筛选、重置、编辑联动、刷新持久化、空状态、新增/详情、手机布局。客户与 Agent 是两个独立本地 Git 仓库；结果没有自动合并到客户 main。

## 需要准确说明的限制

当前编码模型和设计稿解析模型已切换为 `glm-5.3-flash`，识图直接通过已验证的 Coding Plan 入口提交原图并生成设计说明，替换本机 OCR。模型能够解析图片，不代表自动生成结果与设计稿完全一致；原有 OCR 任务记录继续保留作为历史。没有加入 RAG、远程 PR、自动合并、身份权限或操作系统沙箱。

默认 Agent 每个任务只自动执行编译与构建，本次浏览器和目视结果由 Codex 额外验收并明确记录来源。失败任务与分支保留，未伪装成成功。模型密钥位于忽略提交且权限 0600 的本地 `.env`。
