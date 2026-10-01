# Design Agent MVP：前端交互与 UI 设计

日期：2026-09-30。

本目录是本轮新增设计交付。界面里的任务、仓库、检查与分支都是示例，不能证明真实 Agent 开发已成功。

## 方案与交互原型

- [完整前端方案](/Users/RroundRiser/Documents/Reference/design-agent-mvp/Design-to-Code-MVP前端方案.md)
- 原型源：`/Users/RroundRiser/.codex/visualizations/2026/09/30/01a0f2d3-99ed-71b2-90b2-69e42482bd34/design-agent-mvp.html`。这是供 Codex 内联预览的 HTML 片段，包含文件选择、确认层及模拟进度，不是独立部署的完整网站。
- 原型参考截图保存在 `reference/`，分别包含新建、确认、运行、完成、失败和 320px 窄屏视图。

## 高保真 UI 设计图

通过内置 imagegen 工具分三次串行生成。用户已明确接受无法确认具体模型，因此不标称为 Image2.5。三张图均已确认文件为 PNG、尺寸为 1586×992，并视觉核对主要区域。

| 设计图 | 内容 | 对应提示词 |
| --- | --- | --- |
| [新建任务](/Users/RroundRiser/Documents/Reference/design-agent-mvp/design-agent-ui/01-new-task-ui.png) | 两个上传入口、选中文件、仓库、基准分支、确认按钮 | `prompts/01-new-task.txt` |
| [任务运行](/Users/RroundRiser/Documents/Reference/design-agent-mvp/design-agent-ui/02-running-ui.png) | 开发阶段、关键事件、输入摘要、返回入口 | `prompts/02-running.txt` |
| [完成结果](/Users/RroundRiser/Documents/Reference/design-agent-mvp/design-agent-ui/03-completed-ui.png) | 改动摘要、检查状态、未执行验收、未推送分支、报告入口 | `prompts/03-completed.txt` |

第二张以第一张生成图作为风格参考，第三张以第二张作为风格参考；每张同时引用对应交互原型截图。生成图中的文字、按钮位置和布局用于开发参考；代码实现以方案文档的字段、接口和状态为准。

### 新建任务

![新建任务 UI](/Users/RroundRiser/Documents/Reference/design-agent-mvp/design-agent-ui/01-new-task-ui.png)

### 任务运行

![任务运行 UI](/Users/RroundRiser/Documents/Reference/design-agent-mvp/design-agent-ui/02-running-ui.png)

### 完成结果

![完成结果 UI](/Users/RroundRiser/Documents/Reference/design-agent-mvp/design-agent-ui/03-completed-ui.png)

## 验证与未完成项

已验证原型的示例填充、空表单校验、提交确认、返回修改、阶段推进、断网/恢复连接、成功/失败结果与报告展开。320px 视口下布局为单列，根节点没有横向溢出。原型 JavaScript 语法检查通过。

浏览器自动化打开真实文件选择器超时，真实文件选择、拖拽、文件大小及损坏文件的完整验证尚未完成。后台执行、上传 API、Git、轮询、URL 恢复与幂等提交尚未接入；原型中由本地模拟数据演示。
