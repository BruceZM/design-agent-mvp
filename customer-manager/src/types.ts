export const STATUSES = ["待联系", "跟进中", "已成交"] as const;
export type CustomerStatus = (typeof STATUSES)[number];
export interface Customer {
  id: string;
  name: string;
  company: string;
  phone: string;
  status: CustomerStatus;
  notes: string;
  updatedAt: string;
}
export type CustomerDraft = Omit<Customer, "id" | "updatedAt">;
