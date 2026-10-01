// 页面总入口，按阅读顺序包含：简单路由、上传组件、新建任务、任务详情。
// useState 驱动渲染，useRef 保存不需渲染的稳定值，useEffect 管理外部副作用。
// 前端负责提交和展示；模型执行、Git 写入和长任务状态都由后端负责。
import { useCallback, useEffect, useRef, useState } from "react";
import {
  ArrowUpRight,
  ArrowLeft,
  Upload,
  FileText,
  ImagePlus,
  Check,
  Clock,
  GitBranch,
  Layers3,
  Plus,
  RefreshCw,
  X,
  ChevronRight,
  Download,
  Code2,
  CheckCircle2,
  AlertCircle,
  Copy,
  Database,
  FolderGit2,
  LoaderCircle,
} from "lucide-react";
import { request, ApiError, type Health, type Task } from "./api";

// 展示层合并“检查和交付”为一个步骤；真实后端图仍有 check、deliver 两个节点。
// as const 保留字符串字面量类型，避免阶段名称退化成任意 string。
const steps = [
  ["materials", "解析材料"],
  ["prepare", "准备仓库"],
  ["plan", "制定计划"],
  ["develop", "开发代码"],
  ["checks", "检查与交付"],
] as const;
const statusText = {
  queued: "等待开始",
  running: "正在开发",
  succeeded: "代码已交付",
  failed: "任务失败",
};
function usePath() {
  // MVP 只有两个页面，因此用 History API 做最小路由，不引入完整路由库。
  const [path, setPath] = useState(location.pathname);
  useEffect(() => {
    const fn = () => setPath(location.pathname);
    window.addEventListener("popstate", fn);
    // 浏览器后退/前进会触发 popstate；卸载时解绑，避免重复监听。
    return () => window.removeEventListener("popstate", fn);
  }, []);
  const navigate = (to: string) => {
    // pushState 不会主动触发 popstate，所以同时更新 React 中的 path。
    history.pushState({}, "", to);
    setPath(to);
    window.scrollTo(0, 0);
  };
  return { path, navigate };
}
function formatDate(value: string) {
  // 后端存 UTC，toLocaleString 按浏览器时区显示，不改动服务端时间。
  return new Date(value).toLocaleString("zh-CN", {
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
    hour12: false,
  });
}
function readableError(error: unknown) {
  // unknown 需要先判断类型；HTTP 错误展示服务端说明，网络异常给统一提示。
  return error instanceof ApiError
    ? error.message
    : "网络暂时不可用，请确认本地后台服务正在运行";
}
function Modal({
  children,
  onClose,
}: {
  children: React.ReactNode;
  onClose: () => void;
}) {
  // 原生 dialog 的 showModal 提供模态遮罩和焦点管理；ref 用于命令式 API。
  const ref = useRef<HTMLDialogElement>(null);
  useEffect(() => {
    ref.current?.showModal();
    return () => ref.current?.close();
  }, []);
  // Escape 先交给父组件决定是否关闭，父组件可在 busy 时阻止关闭确认框。
  return (
    <dialog
      ref={ref}
      className="modal"
      onCancel={(e) => {
        e.preventDefault();
        onClose();
      }}
    >
      {children}
    </dialog>
  );
}

export default function App() {
  const { path, navigate } = usePath();
  const [health, setHealth] = useState<Health | null>(null);
  // 换页面时刷新服务配置，仅查询配置状态，不会触发模型调用。
  useEffect(() => {
    request<Health>("/api/health")
      .then(setHealth)
      .catch(() => setHealth(null));
  }, [path]);
  const match = path.match(/^\/tasks\/(t-[a-f0-9]{12})$/);
  // 公共壳包含侧栏和顶栏；任务 ID 匹配时渲染详情，否则回到上传工作台。
  return (
    <div className="shell">
      <aside className="sidebar">
        <button className="brand" onClick={() => navigate("/")}>
          <span className="brand-icon">
            <Layers3 size={22} />
          </span>
          <span>
            Design Agent<small>DESIGN TO CODE</small>
          </span>
        </button>
        <span className="nav-caption">工作空间</span>
        <button
          className={`nav-item ${!match ? "active" : ""}`}
          onClick={() => navigate("/")}
        >
          <Plus size={17} />
          新建开发任务
          <ChevronRight size={14} />
        </button>
        <div className="sidebar-note">
          <span className="dot" />
          固定本地仓库<p>青禾 CRM</p>
          <small>每个任务创建独立分支</small>
        </div>
        <div className="sidebar-footer">
          LOCAL MVP <span>v0.1</span>
        </div>
      </aside>
      <div className="workspace">
        <header className="topbar">
          <span>需求开发工作台</span>
          <span className={`service-state ${health ? "connected" : ""}`}>
            <i />
            {health ? "本地服务已连接" : "正在连接本地服务"}
          </span>
        </header>
        <main>
          {match ? (
            <TaskPage id={match[1]} navigate={navigate} />
          ) : (
            <NewTask health={health} navigate={navigate} />
          )}
        </main>
      </div>
    </div>
  );
}

function UploadCard({
  type,
  file,
  onFile,
  error,
  disabled,
}: {
  type: "design" | "prd";
  file: File | null;
  onFile: (file: File | null) => void;
  error: string;
  disabled: boolean;
}) {
  // 同一个组件通过 type 切换图片/PRD；File 保存在父组件，提交时一起上传。
  const [preview, setPreview] = useState("");
  useEffect(() => {
    if (type !== "design" || !file) {
      setPreview("");
      return;
    }
    const url = URL.createObjectURL(file);
    // object URL 只用于本地预览，此时尚未上传；文件改变/卸载时释放引用。
    setPreview(url);
    return () => URL.revokeObjectURL(url);
  }, [file, type]);
  const id = type === "design" ? "design-upload" : "prd-upload";
  // input 的 accept 是选择器提示，真正内容校验在后端 documents.py。
  // label 的 htmlFor 关联原生文件 input，busy 时禁用重选以免请求材料变化。
  return (
    <section className="upload-card">
      <div className="card-label">
        <span className="number">{type === "design" ? "01" : "02"}</span>
        <h2>{type === "design" ? "设计稿" : "产品需求文档"}</h2>
        <span className="required">必需</span>
      </div>
      <input
        id={id}
        type="file"
        accept={
          type === "design" ? ".png,.jpg,.jpeg,.webp" : ".md,.txt,.pdf,.docx"
        }
        disabled={disabled}
        onChange={(e) => onFile(e.target.files?.[0] ?? null)}
        aria-label={type === "design" ? "上传设计稿" : "上传 PRD 文档"}
        className="file-input"
      />
      <label
        className={`upload-zone ${file ? "selected" : ""} ${disabled ? "disabled" : ""}`}
        htmlFor={id}
      >
        {preview ? (
          <img src={preview} alt="已选择的设计稿预览" />
        ) : (
          <span className="upload-icon">
            {type === "design" ? (
              <ImagePlus size={25} />
            ) : (
              <FileText size={25} />
            )}
          </span>
        )}
        <strong>
          {file
            ? file.name
            : type === "design"
              ? "点击上传设计稿"
              : "点击上传 PRD 文档"}
        </strong>
        <span>
          {file
            ? `${(file.size / 1024).toFixed(0)} KB · 已选择，尚未提交`
            : type === "design"
              ? "PNG / JPG / WebP · 最大 5 MB"
              : "MD / TXT / DOCX / 文字 PDF · 最大 20 MB"}
        </span>
        {file ? (
          <small>
            <RefreshCw size={12} />
            点击重新选择
          </small>
        ) : (
          <small>
            <Upload size={12} />
            选择本地文件
          </small>
        )}
      </label>
      {file && !disabled && (
        <button className="remove-file" onClick={() => onFile(null)}>
          <X size={12} />
          移除
        </button>
      )}
      {error && (
        <p className="error" role="alert">
          {error}
        </p>
      )}
    </section>
  );
}

function NewTask({
  health,
  navigate,
}: {
  health: Health | null;
  navigate: (path: string) => void;
}) {
  // confirm 控制二次确认框，busy 控制一次上传请求，二者都不是后台任务状态。
  const [design, setDesign] = useState<File | null>(null),
    [prd, setPrd] = useState<File | null>(null),
    [instructions, setInstructions] = useState(""),
    [confirm, setConfirm] = useState(false),
    [busy, setBusy] = useState(false),
    [error, setError] = useState(""),
    [errors, setErrors] = useState({ design: "", prd: "" }),
    [tasks, setTasks] = useState<Task[]>([]);
  // 同一次提交用稳定 key；sessionStorage 让页面刷新后仍可找回未确认的提交。
  // key 不是 GitHub token 或模型密钥，仅用于后端幂等去重。
  const key = useRef(
    sessionStorage.getItem("design-agent-submission") || crypto.randomUUID(),
  );
  const [recover, setRecover] = useState(
    !!sessionStorage.getItem("design-agent-submission"),
  );
  const refresh = useCallback(
    // useCallback 保持函数引用稳定，避免下方 effect 因每次渲染都换函数而反复执行。
    () =>
      request<{ tasks: Task[] }>("/api/tasks")
        .then((r) => setTasks(r.tasks))
        .catch(() => {}),
    [],
  );
  useEffect(() => {
    refresh();
  }, [refresh]);
  function validate() {
    // 前端快速检查文件名和大小，给即时反馈；无法证明文件内部格式有效。
    let a = "",
      b = "";
    if (!design) a = "请选择一张设计稿";
    else if (
      !/\.(png|jpe?g|webp)$/i.test(design.name) ||
      design.size > 5 * 1024 * 1024
    )
      a = "请上传不超过 5 MB 的 PNG、JPG 或 WebP";
    if (!prd) b = "请选择一份 PRD";
    else if (
      !/\.(md|txt|pdf|docx)$/i.test(prd.name) ||
      prd.size > 20 * 1024 * 1024
    )
      b = "请上传不超过 20 MB 的 MD、TXT、DOCX 或文字 PDF";
    setErrors({ design: a, prd: b });
    return !a && !b;
  }
  function done(task: Task) {
    // 已得到任务 ID 才清理恢复标识并跳转；随后由详情页轮询后台状态。
    sessionStorage.removeItem("design-agent-submission");
    setRecover(false);
    setConfirm(false);
    navigate(`/tasks/${task.id}`);
  }
  async function submit() {
    // busy 防止重复点击；后端仍必须用 key 去重，因为网络层重试不受按钮控制。
    if (!design || !prd || busy) return;
    setBusy(true);
    setError("");
    sessionStorage.setItem("design-agent-submission", key.current);
    // 发送前保存标识：响应丢失或页面刷新后也能查询是否已经创建任务。
    const form = new FormData();
    // 字段名对应后端 submit 参数。浏览器生成 multipart boundary，勿手填 Content-Type。
    form.append("design", design);
    form.append("prd", prd);
    form.append("instructions", instructions);
    form.append("idempotency_key", key.current);
    try {
      done(
        await request<Task>(
          "/api/tasks",
          {
            method: "POST",
            headers: { "X-Design-Agent": "local-mvp" },
            body: form,
          },
          60000,
        ),
      );
    } catch (err) {
      // 非 ApiError 表示没有得到明确 HTTP 结果，服务器可能已经接收成功。
      // 先按原 key 查询；查不到时保留 key，重试仍不会创建第二条同材料任务。
      if (!(err instanceof ApiError)) {
        try {
          done(await request<Task>(`/api/submissions/${key.current}`));
          return;
        } catch {
          /* 原 key 留给重试使用；此处不自动重新 POST 或启动新的模型任务。 */
        }
      }
      setError(readableError(err));
      setRecover(true);
      if (err instanceof ApiError && err.status !== 409) {
        // 明确的校验等错误解除刷新后的恢复提示；409 保留冲突信息供用户处理。
        // 当前组件的 ref 没有重新生成 key，只有成功/重新进入页面才结束此流程。
        sessionStorage.removeItem("design-agent-submission");
        setRecover(false);
      }
    } finally {
      // HTTP 提交结束就解除 busy；后台任务可能还要运行很久。
      setBusy(false);
    }
  }
  async function recoverSubmission() {
    // 恢复只 GET 原提交，不需要重新选择文件，也不会再次调用模型。
    setBusy(true);
    setError("");
    try {
      done(await request<Task>(`/api/submissions/${key.current}`));
    } catch (err) {
      setError(
        err instanceof ApiError && err.status === 404
          ? "还未找到任务。请重新选择相同材料后提交；系统会沿用原提交标识，避免重复任务。"
          : readableError(err),
      );
    } finally {
      setBusy(false);
    }
  }
  // 下面按“材料 → 补充说明 → 确认框 → 最近任务”渲染；仅确认提交调用 submit。
  // JSX 根据状态声明界面，不手动查 DOM 改按钮；文件显示“已选择”不等于已上传。
  return (
    <>
      <div className="breadcrumb">
        工作空间 <span>/</span> 新建开发任务
      </div>
      <section className="page-title">
        <div className="eyebrow">FROM DESIGN TO DELIVERY</div>
        <h1>
          把需求，交给 Agent<span>.</span>
        </h1>
        <p>上传设计稿和 PRD，为青禾 CRM 开发下一项功能。</p>
      </section>
      <div className="new-grid">
        <div>
          <div className="upload-grid">
            <UploadCard
              type="design"
              file={design}
              onFile={setDesign}
              error={errors.design}
              disabled={busy}
            />
            <UploadCard
              type="prd"
              file={prd}
              onFile={setPrd}
              error={errors.prd}
              disabled={busy}
            />
          </div>
          <section className="instructions card">
            <label htmlFor="instructions">
              补充说明 <span>选填</span>
            </label>
            <textarea
              id="instructions"
              maxLength={2000}
              value={instructions}
              disabled={busy}
              placeholder="例如：复用现有客户列表组件，保持新增和编辑功能正常。"
              onChange={(e) => setInstructions(e.target.value)}
            />
            <small>{instructions.length} / 2000</small>
          </section>
          <div className="submit-row">
            <span>
              <GitBranch size={15} />
              在独立分支中完成开发
            </span>
            <button
              className="primary"
              disabled={busy || !health?.configured}
              onClick={() => {
                setError("");
                if (validate()) setConfirm(true);
              }}
            >
              {busy ? (
                <LoaderCircle className="spin" size={17} />
              ) : (
                <ArrowUpRight size={17} />
              )}
              确认材料并开始
            </button>
          </div>
          {!health?.configured && (
            <p className="error">
              {health
                ? "后端模型尚未配置，请在本地 .env 配置密钥。"
                : "本地后台服务尚未连接，请启动项目服务。"}
            </p>
          )}
          {recover && (
            <div className="recovery">
              <span>有一笔提交尚待确认</span>
              <button onClick={recoverSubmission} disabled={busy}>
                <RefreshCw size={14} />
                检查提交状态
              </button>
            </div>
          )}
          {error && (
            <p role="alert" className="error">
              {error}
            </p>
          )}
        </div>
        <aside className="guide card">
          <span className="eyebrow">本次开发目标</span>
          <div className="target">
            <span>
              <FolderGit2 size={22} />
            </span>
            <div>
              <strong>青禾 CRM</strong>
              <small>固定本地应用仓库</small>
            </div>
          </div>
          <div className="target-meta">
            <span>基础分支</span>
            <code>main</code>
          </div>
          <div className="target-meta">
            <span>图片解析</span>
            <code>
              {health ? "多模态识图" : "连接后显示"}
            </code>
          </div>
          <hr />
          <h3>提交之后，会发生什么</h3>
          <ol>
            {steps.map(([s, name], i) => (
              <li key={s}>
                <span>{i + 1}</span>
                <div>
                  <strong>{name}</strong>
                  <small>
                    {
                      [
                        "理解设计稿与 PRD 内容",
                        "创建独立的本地分支",
                        "读取仓库规范，拆解改动",
                        "修改组件、状态和样式",
                        "运行编译与构建，保存报告",
                      ][i]
                    }
                  </small>
                </div>
              </li>
            ))}
          </ol>
          <p className="guide-note">
            <Clock size={15} />
            任务在后台运行，可关闭页面后回来查看。
          </p>
        </aside>
      </div>
      <section className="recent">
        <header>
          <h2>
            最近任务 <span>{tasks.length}</span>
          </h2>
          <button className="text-button" onClick={refresh}>
            <RefreshCw size={13} />
            刷新列表
          </button>
        </header>
        {!tasks.length ? (
          <div className="empty">
            <Layers3 size={27} />
            <p>还没有开发任务</p>
            <small>上传材料，开始第一次需求开发。</small>
          </div>
        ) : (
          <div className="recent-list">
            {tasks.slice(0, 8).map((task) => (
              <button
                key={task.id}
                onClick={() => navigate(`/tasks/${task.id}`)}
              >
                <span className="task-symbol">
                  <Code2 size={18} />
                </span>
                <span>
                  <strong>{task.prd_name}</strong>
                  <small>
                    {task.id} · {formatDate(task.created_at)}
                  </small>
                </span>
                <span className={`badge ${task.status}`}>
                  {statusText[task.status]}
                </span>
                <ChevronRight size={17} />
              </button>
            ))}
          </div>
        )}
      </section>
      {confirm && (
        <Modal
          onClose={() => {
            if (!busy) setConfirm(false);
          }}
        >
          <div className="modal-header">
            <span className="eyebrow">READY TO BUILD</span>
            <button
              className="icon-button"
              aria-label="关闭确认"
              disabled={busy}
              onClick={() => setConfirm(false)}
            >
              <X size={19} />
            </button>
          </div>
          <h2>确认这次开发</h2>
          <p>确认后将使用已配置模型，启动本地后台任务。</p>
          <dl>
            <dt>设计稿</dt>
            <dd>{design?.name}</dd>
            <dt>PRD 文档</dt>
            <dd>{prd?.name}</dd>
            <dt>目标仓库</dt>
            <dd>青禾 CRM / main</dd>
            <dt>补充说明</dt>
            <dd>{instructions || "无"}</dd>
          </dl>
          {error && (
            <p className="error" role="alert">
              {error}
            </p>
          )}
          <footer>
            <button
              className="secondary"
              disabled={busy}
              onClick={() => setConfirm(false)}
            >
              返回修改
            </button>
            <button className="primary" disabled={busy} onClick={submit}>
              {busy ? (
                <LoaderCircle className="spin" size={17} />
              ) : (
                <ArrowUpRight size={17} />
              )}
              {busy ? "正在提交" : "确认提交"}
            </button>
          </footer>
        </Modal>
      )}
    </>
  );
}

function TaskPage({
  id,
  navigate,
}: {
  id: string;
  navigate: (path: string) => void;
}) {
  // connection 描述网页与 API 的连接；task.status 描述后台执行，断网不等于任务失败。
  const [task, setTask] = useState<Task | null>(null),
    [connection, setConnection] = useState<
      "loading" | "connected" | "disconnected"
    >("loading"),
    [error, setError] = useState(""),
    [diff, setDiff] = useState<string | null>(null),
    [showDiff, setShowDiff] = useState(false),
    [copied, setCopied] = useState(false),
    [retry, setRetry] = useState(0);
  useEffect(() => {
    // 每个任务 ID/手动重连各建立一轮轮询；结束时清理定时器并忽略旧响应。
    // cancelled 不强制取消已发出的 fetch，它负责防止旧请求修改新页面状态。
    let cancelled = false;
    let timer: ReturnType<typeof setTimeout>;
    let failures = 0;
    async function poll() {
      try {
        const next = await request<Task>(`/api/tasks/${id}`);
        if (cancelled) return;
        // 服务端 revision 单调递增，网络返回顺序改变时保留较新的快照。
        setTask((old) => (!old || next.revision >= old.revision ? next : old));
        setConnection("connected");
        setError("");
        failures = 0;
        // 先等本轮请求完成再安排下一轮，避免 setInterval 导致多个请求重叠。
        // succeeded/failed 时停止常规轮询，页面直接保留最终快照。
        if (next.status === "queued" || next.status === "running")
          timer = setTimeout(poll, 3000);
      } catch (err) {
        if (cancelled) return;
        setConnection("disconnected");
        setError(readableError(err));
        if (err instanceof ApiError && err.status === 404) return;
        // 临时断网渐进等待，最多 15 秒；任务不存在则停止请求。
        failures++;
        timer = setTimeout(poll, Math.min(15000, 3000 * failures));
      }
    }
    poll();
    return () => {
      cancelled = true;
      clearTimeout(timer);
    };
  }, [id, retry]);
  async function loadDiff() {
    // 按需读取纯文本差异并缓存，避免每次轮询重复下载较大的 diff。
    setShowDiff(!showDiff);
    if (diff === null) {
      try {
        const response = await fetch(`/api/tasks/${id}/artifacts/changes.diff`);
        if (!response.ok) throw Error();
        setDiff(await response.text());
      } catch {
        setDiff("代码差异尚不可用，请稍后重试");
      }
    }
  }
  // 后台 deliver/completed/checks_failed 都归入页面的“检查与交付”。
  // interrupted 使用原阶段定位失败步骤，避免把服务重启误画成材料校验失败。
  const displayedPhase =
    task?.phase === "interrupted"
      ? task.interrupted_phase
      : ["deliver", "completed", "checks_failed"].includes(task?.phase ?? "")
        ? "checks"
        : task?.phase;
  const phaseIndex = task
    ? steps.findIndex(([key]) => key === displayedPhase)
    : -1;
  const completed = task?.status === "succeeded";
  const terminal = completed || task?.status === "failed";
  // succeeded 仅表示源码变化且编译/构建通过；checks 中的 not_run 仍需展示。
  const checks = task?.checks ?? [];
  // 详情依次渲染阶段、seq 有序日志、计划和结果。下载按钮只引用后端提供的产物。
  // diff 放在 pre 的文本节点里，React 会转义，不把生成代码当 HTML 执行。
  return (
    <>
      <button className="back-link" onClick={() => navigate("/")}>
        <ArrowLeft size={15} />
        返回工作台
      </button>
      <div className="task-title">
        <div>
          <span className="eyebrow">DEVELOPMENT TASK</span>
          <h1>
            {task ? statusText[task.status] : "加载任务"}
            <span>.</span>
          </h1>
          <p>
            {task?.prd_name || id} <code>{id}</code>
          </p>
        </div>
        <span className={`badge ${task?.status ?? "queued"}`}>
          {task ? statusText[task.status] : "正在读取"}
        </span>
      </div>
      {connection === "disconnected" && (
        <div className="connection-alert" role="alert">
          <AlertCircle size={17} />
          <span>{error}。当前连接中断，任务状态以后台记录为准。</span>
          <button onClick={() => setRetry((x) => x + 1)}>重新连接</button>
        </div>
      )}
      {task && (
        <>
          <div className="task-meta">
            <span>
              <FolderGit2 size={16} />
              青禾 CRM
            </span>
            <span>
              <Clock size={16} />
              {formatDate(task.created_at)}
            </span>
            <span>
              <Database size={15} />
              {connection === "connected" ? "后台状态已同步" : "等待重新同步"}
            </span>
          </div>
          <div className="task-grid">
            <section className="steps card">
              <h2>开发流程</h2>
              <ol>
                {steps.map(([key, name], i) => {
                  // 视觉状态由终态和阶段索引派生，不建立另一份容易不同步的进度状态。
                  const done = completed || i < phaseIndex;
                  const active =
                    !terminal && task.status === "running" && i === phaseIndex;
                  const failed = task.status === "failed" && i === phaseIndex;
                  return (
                    <li
                      key={key}
                      className={`${done ? "done" : ""} ${active ? "current" : ""} ${failed ? "broken" : ""}`}
                    >
                      <span className="step-dot">
                        {done ? (
                          <Check size={15} />
                        ) : failed ? (
                          <X size={15} />
                        ) : active ? (
                          <LoaderCircle className="spin" size={16} />
                        ) : (
                          i + 1
                        )}
                      </span>
                      <div>
                        <strong>{name}</strong>
                        <small>
                          {done
                            ? "已完成"
                            : failed
                              ? "执行失败"
                              : active
                                ? "正在执行"
                                : task.status === "queued" && i === 0
                                  ? "等待后台开始"
                                  : "等待执行"}
                        </small>
                      </div>
                    </li>
                  );
                })}
              </ol>
              <p>任务在后台持续运行，页面关闭不影响执行。</p>
              {task.branch && (
                <div className="branch-card">
                  <GitBranch size={16} />
                  <code>{task.branch}</code>
                  <button
                    className="icon-button"
                    aria-label="复制分支名"
                    onClick={() =>
                      navigator.clipboard
                        .writeText(task.branch!)
                        .then(() => setCopied(true))
                        .catch(() => setCopied(false))
                    }
                  >
                    <Copy size={13} />
                  </button>
                  {copied && <small>已复制</small>}
                </div>
              )}
            </section>
            <div>
              <section className="activity card">
                <header>
                  <h2>任务动态</h2>
                  <span>
                    <i className={terminal ? "" : "pulse"} />
                    {terminal ? "已结束" : "后台记录"}
                  </span>
                </header>
                <div className="log-list" aria-live="polite">
                  {task.events?.map((e) => (
                    <div key={e.seq}>
                      <time>
                        {new Date(e.at).toLocaleTimeString("zh-CN", {
                          hour12: false,
                        })}
                      </time>
                      <span>{e.message}</span>
                    </div>
                  ))}
                </div>
              </section>
              {task.plan && (
                <section className="plan card">
                  <h2>开发计划</h2>
                  <p>{task.plan.summary}</p>
                  <ul>
                    {task.plan.steps.map((s, i) => (
                      <li key={i}>{s}</li>
                    ))}
                  </ul>
                </section>
              )}
              {terminal && (
                <section className="result card">
                  <div className="result-heading">
                    {completed ? (
                      <CheckCircle2 size={24} />
                    ) : (
                      <AlertCircle size={24} />
                    )}
                    <div>
                      <h2>{completed ? "本地代码交付已保存" : "任务未完成"}</h2>
                      <p>
                        {completed
                          ? checks.some(
                              (c) =>
                                c.name === "browser_functional" &&
                                c.status === "passed",
                            )
                            ? "编译、构建及本次浏览器验收通过，详情见交付记录。"
                            : "编译与构建通过，功能和视觉需单独验收。"
                          : "已有材料、日志和分支均保留，可查看报告定位问题。"}
                      </p>
                    </div>
                  </div>
                  {task.error && (
                    <p className="error error-box">{task.error}</p>
                  )}
                  <div className="check-list">
                    {checks.map((c) => (
                      <div key={c.name}>
                        <span>
                          {(
                            {
                              typecheck: "TypeScript 编译",
                              build: "生产构建",
                              browser_functional: "浏览器功能验收",
                              visual_review: "UI 视觉验收",
                            } as Record<string, string>
                          )[c.name] || c.name}
                        </span>
                        <strong className={c.status}>
                          {
                            {
                              passed: "通过",
                              failed: "失败",
                              not_run: "未执行",
                            }[c.status]
                          }
                        </strong>
                      </div>
                    ))}
                  </div>
                  {task.report?.changed_files && (
                    <p className="files-summary">
                      修改 {task.report.changed_files.length} 个文件 · 模型调用{" "}
                      {task.report.model_calls ?? 0} 次 · 本地分支
                    </p>
                  )}
                  <div className="result-actions">
                    {checks.some(
                      (c) => c.name === "build" && c.status === "passed",
                    ) && (
                      <a
                        className="primary"
                        target="_blank"
                        rel="noreferrer"
                        href={`/api/tasks/${id}/preview/`}
                      >
                        <ArrowUpRight size={16} />
                        打开应用预览
                      </a>
                    )}
                    {task.artifacts?.includes("changes.diff") && (
                      <button className="secondary" onClick={loadDiff}>
                        <Code2 size={15} />
                        {showDiff ? "收起" : "查看"}代码差异
                      </button>
                    )}
                    {task.artifacts?.includes("report.md") && (
                      <a
                        className="secondary"
                        href={`/api/tasks/${id}/artifacts/report.md`}
                      >
                        <Download size={15} />
                        下载报告
                      </a>
                    )}
                  </div>
                  {showDiff && <pre className="diff">{diff ?? "读取中…"}</pre>}
                  <details className="artifacts">
                    <summary>
                      全部交付文件 ({task.artifacts?.length ?? 0})
                    </summary>
                    {task.artifacts?.map((name) => (
                      <a key={name} href={`/api/tasks/${id}/artifacts/${name}`}>
                        <FileText size={14} />
                        {name}
                        <Download size={13} />
                      </a>
                    ))}
                  </details>
                </section>
              )}
            </div>
          </div>
        </>
      )}
      <footer className="page-footer">Design Agent · 固定仓库开发 MVP</footer>
    </>
  );
}
