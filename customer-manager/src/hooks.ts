import { useState } from "react";
import { isCustomer, seedCustomers } from "./data";
import type { Customer, CustomerDraft } from "./types";
const STORAGE_KEY = "qinghe-crm-customers-v1";
function loadCustomers(): Customer[] {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return seedCustomers;
    const data: unknown = JSON.parse(raw);
    return Array.isArray(data) && data.every(isCustomer) ? data : seedCustomers;
  } catch {
    return seedCustomers;
  }
}
export function useCustomers() {
  const [customers, setCustomers] = useState<Customer[]>(loadCustomers);
  const saveCustomer = (draft: CustomerDraft, id?: string) => {
    const customer: Customer = {
      ...draft,
      name: draft.name.trim(),
      company: draft.company.trim(),
      phone: draft.phone.trim(),
      id: id ?? crypto.randomUUID(),
      updatedAt: new Date().toLocaleDateString("sv-SE"),
    };
    if (!customer.name) throw new Error("请填写客户姓名");
    const next = id
      ? customers.map((c) => (c.id === id ? customer : c))
      : [customer, ...customers];
    // Only update the screen after storage succeeds, so an error cannot look like a saved record.
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(next));
    } catch {
      throw new Error(
        "浏览器存储不可用，客户尚未保存。请检查存储空间或浏览器设置。",
      );
    }
    setCustomers(next);
    return customer;
  };
  return { customers, saveCustomer };
}
