import { useState } from "react";
import { ChevronLeft, ChevronRight, Pencil, ArrowUpRight } from "lucide-react";
import { STATUSES, type Customer } from "../types";
interface Props {
  customers: Customer[];
  onView: (c: Customer) => void;
  onEdit: (c: Customer) => void;
}
const PAGE_SIZE = 8;
export function CustomerList({ customers, onView, onEdit }: Props) {
  const [page, setPage] = useState(1);
  const totalPages = Math.max(1, Math.ceil(customers.length / PAGE_SIZE));
  const currentPage = Math.min(page, totalPages);
  const rows = customers.slice(
    (currentPage - 1) * PAGE_SIZE,
    currentPage * PAGE_SIZE,
  );
  return (
    <section className="list-card" aria-label="客户列表">
      <div className="list-heading">
        <h2>
          全部客户 <span>{customers.length}</span>
        </h2>
        <span className="muted">及时更新，让跟进更有序</span>
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
          <h3>还没有客户</h3>
          <p>点击「新增客户」，建立第一份客户档案。</p>
        </div>
      )}
      <footer className="pagination">
        <span>
          共 {customers.length} 位客户 · 每页 {PAGE_SIZE} 条
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
