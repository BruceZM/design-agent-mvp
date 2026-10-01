import { useEffect, useRef, useState } from "react";
import {
  Building2,
  Phone,
  X,
  Pencil,
  UserRound,
  NotebookPen,
} from "lucide-react";
import { STATUSES, type Customer, type CustomerDraft } from "../types";
interface Props {
  customer?: Customer;
  mode: "view" | "edit" | "new";
  onClose: () => void;
  onEdit: () => void;
  onSave: (draft: CustomerDraft, id?: string) => void;
}
export function CustomerPanel({
  customer,
  mode,
  onClose,
  onEdit,
  onSave,
}: Props) {
  const [draft, setDraft] = useState<CustomerDraft>(
    customer ?? {
      name: "",
      company: "",
      phone: "",
      status: "待联系",
      notes: "",
    },
  );
  const [error, setError] = useState("");
  const panel = useRef<HTMLElement>(null);
  const view = mode === "view";
  useEffect(() => {
    const previous = document.activeElement as HTMLElement | null;
    const root = panel.current;
    root?.querySelector<HTMLElement>(view ? "button" : "input")?.focus();
    const handleKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") onClose();
      if (event.key !== "Tab" || !root) return;
      const focusable = Array.from(
        root.querySelectorAll<HTMLElement>("button,input,select,textarea"),
      ).filter((el) => !el.hasAttribute("disabled"));
      const first = focusable[0],
        last = focusable[focusable.length - 1];
      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault();
        last?.focus();
      }
      if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault();
        first?.focus();
      }
    };
    document.addEventListener("keydown", handleKey);
    return () => {
      document.removeEventListener("keydown", handleKey);
      previous?.focus();
    };
  }, [view, onClose]);
  function update<K extends keyof CustomerDraft>(
    key: K,
    value: CustomerDraft[K],
  ) {
    setDraft((old) => ({ ...old, [key]: value }));
    setError("");
  }
  return (
    <div
      className="backdrop"
      onMouseDown={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
    >
      <section
        className="customer-panel"
        role="dialog"
        aria-modal="true"
        aria-labelledby="panel-title"
        ref={panel}
      >
        <header className="panel-header">
          <div>
            <span className="eyebrow">客户档案</span>
            <h2 id="panel-title">
              {view ? "客户详情" : mode === "new" ? "新增客户" : "编辑客户"}
            </h2>
          </div>
          <button
            className="icon-button"
            aria-label="关闭抽屉"
            onClick={onClose}
          >
            <X size={20} />
          </button>
        </header>
        {view ? (
          <div className="panel-body">
            <div className="profile">
              <span className="avatar large">{customer?.name.slice(-2)}</span>
              <h3>{customer?.name}</h3>
              <span
                className={`status status-${STATUSES.indexOf(draft.status)}`}
              >
                {draft.status}
              </span>
            </div>
            <dl className="details">
              <dt>
                <Building2 size={16} />
                公司
              </dt>
              <dd>{draft.company || "尚未填写"}</dd>
              <dt>
                <Phone size={16} />
                联系电话
              </dt>
              <dd>{draft.phone || "尚未填写"}</dd>
              <dt>
                <NotebookPen size={16} />
                跟进备注
              </dt>
              <dd className="notes">{draft.notes || "尚无跟进记录"}</dd>
              <dt>最近更新</dt>
              <dd>{customer?.updatedAt}</dd>
            </dl>
            <button className="primary wide" onClick={onEdit}>
              <Pencil size={16} /> 编辑客户
            </button>
          </div>
        ) : (
          <form
            onSubmit={(e) => {
              e.preventDefault();
              try {
                onSave(draft, customer?.id);
              } catch (err) {
                setError(err instanceof Error ? err.message : "保存失败");
              }
            }}
          >
            <div className="panel-body">
              <p className="muted">维护客户基本信息与跟进记录。</p>
              <label htmlFor="customer-name">
                <UserRound size={15} />
                客户姓名 <span className="required">*</span>
              </label>
              <input
                id="customer-name"
                value={draft.name}
                maxLength={50}
                required
                placeholder="请输入客户姓名"
                onChange={(e) => update("name", e.target.value)}
              />
              <label htmlFor="customer-company">公司</label>
              <input
                id="customer-company"
                value={draft.company}
                maxLength={100}
                placeholder="请输入公司名称"
                onChange={(e) => update("company", e.target.value)}
              />
              <label htmlFor="customer-phone">联系电话</label>
              <input
                id="customer-phone"
                value={draft.phone}
                maxLength={40}
                type="tel"
                placeholder="请输入联系电话"
                onChange={(e) => update("phone", e.target.value)}
              />
              <label htmlFor="customer-status">跟进状态</label>
              <select
                id="customer-status"
                value={draft.status}
                onChange={(e) =>
                  update("status", e.target.value as CustomerDraft["status"])
                }
              >
                {STATUSES.map((s) => (
                  <option key={s}>{s}</option>
                ))}
              </select>
              <label htmlFor="customer-notes">跟进备注</label>
              <textarea
                id="customer-notes"
                rows={5}
                value={draft.notes}
                maxLength={2000}
                placeholder="记录需求、沟通进展与下一步计划"
                onChange={(e) => update("notes", e.target.value)}
              />
              {error && (
                <p className="error" role="alert">
                  {error}
                </p>
              )}
            </div>
            <footer className="panel-footer">
              <button type="button" className="secondary" onClick={onClose}>
                取消
              </button>
              <button className="primary" type="submit">
                保存客户
              </button>
            </footer>
          </form>
        )}
      </section>
    </div>
  );
}
