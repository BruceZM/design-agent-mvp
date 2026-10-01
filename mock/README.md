# Mock 需求材料索引

按材料类型分别保存 PRD 和 UI，同一需求用相同编号配对。

```text
mock/
├── README.md
├── prd/
│   └── feature-prd-1.md
└── ui/
    ├── feature-ui-1.png
    └── feature-ui-1.prompt.txt
```

## 需求索引

| 配对编号 | 需求 | 版本 | PRD | UI 设计稿 | 生图提示词 |
| --- | --- | --- | --- | --- | --- |
| feature-1 | 客户关键词搜索 | 1.0 | [feature-prd-1.md](prd/feature-prd-1.md) | [feature-ui-1.png](ui/feature-ui-1.png) | [feature-ui-1.prompt.txt](ui/feature-ui-1.prompt.txt) |

## 后续命名规则

- 新需求依次增加编号，例如 `prd/feature-prd-2.md` 与 `ui/feature-ui-2.png`。
- 同一需求迭代保留原编号并追加版本后缀，例如 `prd/feature-prd-1-v2.md` 与 `ui/feature-ui-1-v2.png`。无后缀的现有文件代表第一版；保留历史材料，不覆盖旧版。
- 提示词跟随 UI 文件名，例如 `ui/feature-ui-1-v2.prompt.txt`。
- 每次新增材料更新上面的索引表。提交时选择同一编号、同一版本的 PRD 和 UI。

## 上传方式

打开 http://127.0.0.1:8011 ，在「新建开发任务」中：

1. 「设计稿」选择 `mock/ui/feature-ui-1.png`。
2. 「产品需求文档」选择 `mock/prd/feature-prd-1.md`。
3. 补充说明可留空，确认提交。

开发目标是本地 `customer-manager` 的 `main` 分支；正常提交后由 Agent 创建独立工作区和任务分支。本次创建 mock 文件本身不会提交或运行开发任务。

## 当前需求说明

当前需求为青禾 CRM 增加「姓名 / 公司 / 手机号关键词搜索」。PRD 包含匹配规则、视觉要求、边界行为和 12 项验收用例。配套桌面设计稿展示搜索「青禾」后的六条结果；使用内置 imagegen 工具生成，未确认具体模型型号，完整提示词与 UI 一起保存。

测试数据来自当前仓库的演示种子客户，没有使用真实客户资料。验收数量以未改动的 24 条种子数据为准；浏览器已有编辑数据时，结果可能不同。PRD 是精确交互依据，设计稿是视觉参考。
