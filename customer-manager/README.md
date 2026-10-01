# 青禾 CRM · 下游 MVP

一个独立的本地 Git 仓库，专门用于 Design Agent 的需求增量开发。

```sh
npm ci
npm run dev
```

访问 http://127.0.0.1:5174 。检查：`npm run typecheck`、`npm run build`。

功能：客户列表和 8 条分页、详情、新增和编辑、localStorage 持久化、手机卡片布局。所有种子资料都是演示数据。基线 `main` 没有状态筛选。

## 开发规则（Agent 必须阅读）

- React + TypeScript + Vite，样式在 `src/styles.css`，组件在 `src/components/`，类型在 `src/types.ts`，数据在 `src/data.ts`，数据读写在 `src/hooks.ts`。
- 优先复用现有 `CustomerList`、`CustomerPanel`、`useCustomers` 和 `STATUSES`，保持中文标签和青绿视觉风格。
- 增量需求只修改 `src/`。不改依赖、构建脚本、配置、Git 或原型文档；不请求外部服务、不新增登录和后台。
- 修改后运行 typecheck 和 build。功能必须进行浏览器验证；编译成功不能当作视觉验收通过。
- 演示数据在当前浏览器保存。写入失败必须反馈错误；不得显示假的成功提示。
- 新组件使用 PascalCase，新函数/变量使用 camelCase；保持严格类型，不使用 `any` 掩盖错误。

原型与 UI 稿位于 `docs/`。Agent 任务在独立 worktree 分支上开发，`main` 保持基线，可随时对照。
