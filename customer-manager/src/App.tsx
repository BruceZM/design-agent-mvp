import { useCallback, useState } from "react";
import { UsersRound, Plus, Leaf, Database, ArrowUpRight } from "lucide-react";
import { useCustomers } from "./hooks";
import { CustomerList } from "./components/CustomerList";
import { CustomerPanel } from "./components/CustomerPanel";
import type { Customer } from "./types";
export default function App() {
  const { customers, saveCustomer } = useCustomers();
  const [panel, setPanel] = useState<{
    mode: "new" | "view" | "edit";
    customer?: Customer;
  } | null>(null);
  const [notice, setNotice] = useState("");
  const close = useCallback(() => setPanel(null), []);
  return (
    <div className="app-shell">
      <aside className="sidebar">
        <a className="brand" href="/">
          <span className="brand-mark">
            <Leaf size={22} />
          </span>
          <span>
            青禾<span className="brand-sub">CRM</span>
          </span>
        </a>
        <span className="nav-label">工作空间</span>
        <div className="nav-item">
          <UsersRound size={18} />
          客户档案
        </div>
        <div className="sidebar-bottom">
          <span className="local-dot" />
          本地演示版本<small>让每一份客户关系，都有迹可循。</small>
        </div>
      </aside>
      <main className="main-content">
        <div className="breadcrumb">
          工作空间 <span>/</span> 客户档案
        </div>
        <header className="page-header">
          <div>
            <span className="eyebrow">CUSTOMER WORKSPACE</span>
            <h1>
              客户档案<span className="title-dot">.</span>
            </h1>
            <p>维护客户信息，记录每一次跟进。</p>
          </div>
          <button
            className="primary"
            onClick={() => {
              setNotice("");
              setPanel({ mode: "new" });
            }}
          >
            <Plus size={18} />
            新增客户
          </button>
        </header>
        {notice && (
          <div className="notice" role="status">
            {notice}
            <button className="text-button" onClick={() => setNotice("")}>
              关闭
            </button>
          </div>
        )}
        <CustomerList
          customers={customers}
          onView={(c) => setPanel({ mode: "view", customer: c })}
          onEdit={(c) => setPanel({ mode: "edit", customer: c })}
        />
        <footer className="page-footer">
          <span>
            <Database size={14} />
            演示数据保存在当前浏览器
          </span>
          <span>
            青禾 CRM · MVP <ArrowUpRight size={13} />
          </span>
        </footer>
      </main>
      {panel && (
        <CustomerPanel
          key={`${panel.mode}-${panel.customer?.id ?? "new"}`}
          customer={panel.customer}
          mode={panel.mode}
          onClose={close}
          onEdit={() => setPanel({ ...panel, mode: "edit" })}
          onSave={(draft, id) => {
            saveCustomer(draft, id);
            close();
            setNotice(id ? "客户信息已更新" : "客户已创建");
          }}
        />
      )}
    </div>
  );
}
