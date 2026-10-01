import { STATUSES, type Customer } from "./types";
const names = [
  "林若安",
  "陈予川",
  "许知远",
  "周沐晴",
  "沈亦宁",
  "顾言初",
  "唐可欣",
  "陆景行",
  "宋一诺",
  "何云舒",
  "江亦辰",
  "白予宁",
  "梁星河",
  "赵嘉禾",
  "温书意",
  "韩清越",
  "李言希",
  "郑南星",
  "夏知夏",
  "王时安",
  "蔡明远",
  "丁语桐",
  "方澄",
  "孟青",
];
export const seedCustomers: Customer[] = names.map((name, i) => ({
  id: `demo-${i + 1}`,
  name,
  company: ["青禾科技", "向野设计", "松石贸易", "澄远咨询"][i % 4],
  phone: `1380000${String(i).padStart(4, "0")}`,
  status: STATUSES[i % 3],
  notes:
    i % 2
      ? "已完成首次沟通，待确认下一步合作需求。"
      : "计划本周联系，了解业务需求与合作时间。",
  updatedAt: "2026-10-01",
}));
export function isCustomer(value: unknown): value is Customer {
  if (!value || typeof value !== "object") return false;
  const x = value as Record<string, unknown>;
  return (
    ["id", "name", "company", "phone", "notes", "updatedAt"].every(
      (k) => typeof x[k] === "string",
    ) && STATUSES.includes(x.status as Customer["status"])
  );
}
