import { useMemo, useState } from "react";
import { ChevronLeft, ChevronRight, Pencil, ArrowUpRight } from "lucide-react";
import { STATUSES, type Customer, type CustomerStatus } from "../types";

export type StatusFilter = CustomerStatus | "全部状态";
const FILTER_OPTIONS: StatusFilter[] = ["全部状态", ...STATUSES];

interface Props {
  customers: Customer[];
  onView: (c: Customer) => void;
  onEdit: (c: Customer) => void;
}
const PAGE_SIZE = 8;
export function CustomerList({ customers, onView, onEdit }: Props) {
  const [statusFilter, setStatusFilter] = useState<StatusFilter>("全部状态");
  const [page, setPage] = useState(1);
  const filtered = useMemo(
    () =>
      statusFilter === "全部状态"
        ? customers
        : customers.filter((c) => c.status === statusFilter),
    [customers, statusFilter],
  );
  const totalPages = Math.max(1, Math.ceil(filtered.length / PAGE_SIZE));
  const currentPage = Math.min(page, totalPages);
  const rows = filtered.slice(
    (currentPage - 1) * PAGE_SIZE,
    currentPage * PAGE_SIZE,
  );
  return (
    <section className="list-card" aria-label="客户列表">
      <div className="list-heading">
        <h2>
          全部客户 <span>{filtered.length}</span>
        </h2>
        <span className="muted">及时更新，让跟进更有序</span>
      </div>
      <div className="filter-bar">
        <label htmlFor="status-filter">跟进状态</label>
        <select
          id="status-filter"
          value={statusFilter}
          onChange={(e) => {
            setStatusFilter(e.target.value as StatusFilter);
            setPage(1);
          }}
        >
          {FILTER_OPTIONS.map((option) => (
            <option key={option} value={option}>
              {option}
            </option>
          ))}
        </select>
        <button
          type="button"
          className="text-button reset-button"
          onClick={() => {
            setStatusFilter("全部状态");
            setPage(1);
          }}
        >
          重置
        </button>
      </div>
      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th>客户</th>
              <th>公司</th>
              <th>联系方式</th>
              <th>跟进状态</th>
              <th>最近更新</th>
              <th>
                <span className="sr-only">操作</span>
              </th>
            </tr>
          </thead>
          <tbody>
            {rows.map((c, i) => (
              <tr key={c.id}>
                <td>
                  <button className="name-button" onClick={() => onView(c)}>
                    <span className={`avatar color-${i % 4}`}>
                      {c.name.slice(-2)}
                    </span>
                    <span>{c.name}</span>
                  </button>
                </td>
                <td>{c.company || "—"}</td>
                <td className="phone">{c.phone || "—"}</td>
                <td>
                  <span
                    className={`status status-${STATUSES.indexOf(c.status)}`}
                  >
                    {c.status}
                  </span>
                </td>
                <td className="muted">{c.updatedAt}</td>
                <td>
                  <button
                    className="text-button"
                    aria-label={`编辑 ${c.name}`}
                    onClick={() => onEdit(c)}
                  >
                    <Pencil size={14} />
                    编辑
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <div className="customer-cards">
        {rows.map((c) => (
          <article key={c.id}>
            <button className="mobile-customer" onClick={() => onView(c)}>
              <span className="avatar">{c.name.slice(-2)}</span>
              <span>
                <strong>{c.name}</strong>
                <small>{c.company || "暂无公司"}</small>
              </span>
              <ArrowUpRight size={17} />
            </button>
            <div className="mobile-bottom">
              <span className={`status status-${STATUSES.indexOf(c.status)}`}>
                {c.status}
              </span>
              <button
                className="text-button"
                onClick={() => onEdit(c)}
                aria-label={`编辑 ${c.name}`}
              >
                编辑
              </button>
            </div>
          </article>
        ))}
      </div>
      {!rows.length && (
        <div className="empty">
          <h3>没有符合条件的客户</h3>
          <p>请调整「跟进状态」筛选或点击「重置」查看全部客户。</p>
        </div>
      )}
      <footer className="pagination">
        <span>
          共 {filtered.length} 位客户 · 每页 {PAGE_SIZE} 条
        </span>
        <div>
          <button
            aria-label="上一页"
            className="icon-button"
            disabled={currentPage === 1}
            onClick={() => setPage(currentPage - 1)}
          >
            <ChevronLeft size={18} />
          </button>
          <span aria-label="当前页">
            {currentPage} / {totalPages}
          </span>
          <button
            aria-label="下一页"
            className="icon-button"
            disabled={currentPage === totalPages}
            onClick={() => setPage(currentPage + 1)}
          >
            <ChevronRight size={18} />
          </button>
        </div>
      </footer>
    </section>
  );
}
