# 任务持久化层：tasks 为当前快照，events 为按任务排列的过程日志。
# 所有 SQL 的用户值通过占位参数传入，不拼接进 SQL 字符串。
import json
import sqlite3
import threading
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path


def now() -> str:
    # 持久化统一用 UTC ISO 时间；前端负责转换成用户的本地显示格式。
    return datetime.now(UTC).isoformat()


class Store:
    def __init__(self, path: Path):
        path.parent.mkdir(parents=True, exist_ok=True)
        self.path = path
        self.lock = threading.RLock()
        # RLock 允许同线程嵌套加锁：submit 持锁时还会调用 create。
        # 这是单进程互斥，不能直接把本 MVP 改成多个 Worker 进程并发执行。
        with self.connect() as db:
            # WAL 提升读写并存能力，SQLite 仍串行写入。
            # 固定检索字段单独存列，计划/检查等动态字段存 JSON，简化 MVP schema。
            db.executescript("""PRAGMA journal_mode=WAL;
            CREATE TABLE IF NOT EXISTS tasks (id TEXT PRIMARY KEY, key TEXT UNIQUE NOT NULL, fingerprint TEXT NOT NULL, status TEXT NOT NULL, phase TEXT NOT NULL, created_at TEXT NOT NULL, updated_at TEXT NOT NULL, revision INTEGER NOT NULL, data TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS events (task_id TEXT NOT NULL, seq INTEGER NOT NULL, at TEXT NOT NULL, phase TEXT NOT NULL, message TEXT NOT NULL, PRIMARY KEY(task_id,seq));""")

    @contextmanager
    def connect(self):
        # 每次操作开独立连接，避免 HTTP 线程和 Worker 共用同一个连接。
        # with db 正常提交、异常回滚，finally 确保关闭；timeout 是等数据库锁的秒数。
        db = sqlite3.connect(self.path, timeout=10)
        db.row_factory = sqlite3.Row
        try:
            with db:
                yield db
        finally:
            db.close()

    @staticmethod
    def decode(row):
        # 把动态 data 合并进任务字典，但不给网页返回提交 key 和材料 fingerprint。
        if row is None:
            return None
        task = dict(row)
        task.update(json.loads(task.pop("data")))
        task.pop("key", None)
        task.pop("fingerprint", None)
        return task

    def get(self, task_id):
        # 单任务查询；不存在返回 None，由 API 决定 HTTP 404 的说明。
        with self.connect() as db:
            return self.decode(
                db.execute("SELECT * FROM tasks WHERE id=?", (task_id,)).fetchone()
            )

    def by_key(self, key):
        # 幂等查询额外返回内部指纹，submit 用它区分“同一次重试”和“材料已变”。
        with self.connect() as db:
            row = db.execute("SELECT * FROM tasks WHERE key=?", (key,)).fetchone()
            return (self.decode(row), row["fingerprint"]) if row else (None, None)

    def create(self, task_id, key, fingerprint, data):
        # 插入 queued 和首条事件在同一事务内完成，避免出现无日志的半成任务。
        # key UNIQUE 是数据库层约束；API 的锁还保护“查询后再插入”的整段逻辑。
        with self.lock, self.connect() as db:
            at = now()
            db.execute(
                "INSERT INTO tasks VALUES (?,?,?,?,?,?,?,?,?)",
                (
                    task_id,
                    key,
                    fingerprint,
                    "queued",
                    "queued",
                    at,
                    at,
                    1,
                    json.dumps(data, ensure_ascii=False),
                ),
            )
            db.execute(
                "INSERT INTO events VALUES (?,?,?,?,?)",
                (task_id, 1, at, "queued", "任务已进入本地后台队列"),
            )
        return self.get(task_id)

    def update(self, task_id, **changes):
        # status/phase 更新独立列，剩余字段并入 JSON；旧字段未提供就保留。
        # revision 是变化版本号，前端据此拒绝过期快照覆盖新状态。
        with self.lock, self.connect() as db:
            row = db.execute("SELECT * FROM tasks WHERE id=?", (task_id,)).fetchone()
            data = json.loads(row["data"])
            status = changes.pop("status", row["status"])
            phase = changes.pop("phase", row["phase"])
            data.update(changes)
            db.execute(
                "UPDATE tasks SET status=?, phase=?, updated_at=?, revision=revision+1, data=? WHERE id=?",
                (status, phase, now(), json.dumps(data, ensure_ascii=False), task_id),
            )

    def event(self, task_id, phase, message):
        # 同一锁内分配 seq 并插入，保证每个任务的事件序号递增且不重复。
        # 追加日志也提高 revision，即使阶段没变，前端仍能收到新的任务版本。
        with self.lock, self.connect() as db:
            seq = db.execute(
                "SELECT COALESCE(MAX(seq),0)+1 FROM events WHERE task_id=?", (task_id,)
            ).fetchone()[0]
            db.execute(
                "INSERT INTO events VALUES (?,?,?,?,?)",
                (task_id, seq, now(), phase, message[:5000]),
            )
            db.execute(
                "UPDATE tasks SET revision=revision+1, updated_at=? WHERE id=?",
                (now(), task_id),
            )

    def events(self, task_id):
        # 按 seq 而不是时间排序，多个事件落在同一时刻也有确定顺序。
        with self.connect() as db:
            return [
                dict(r)
                for r in db.execute(
                    "SELECT * FROM events WHERE task_id=? ORDER BY seq", (task_id,)
                )
            ]

    def list(self):
        # 页面只需最近 50 条；pending() 单独查询全部排队任务，不受此限制。
        with self.connect() as db:
            return [
                self.decode(r)
                for r in db.execute(
                    "SELECT * FROM tasks ORDER BY created_at DESC LIMIT 50"
                )
            ]

    def pending(self):
        # 队列是数据库中的 queued 状态，没有独立内存队列副本。
        with self.connect() as db:
            return [
                r["id"]
                for r in db.execute(
                    "SELECT id FROM tasks WHERE status='queued' ORDER BY created_at"
                )
            ]

    def interrupt_running(self):
        # 当前实现只遍历 list() 的最近 50 条；这是本地 MVP 的恢复边界。
        # 记录中断前 phase 供前端定位，保留分支/产物，不从 LangGraph 节点续跑。
        for task in self.list():
            if task["status"] == "running":
                self.update(
                    task["id"],
                    status="failed",
                    phase="interrupted",
                    interrupted_phase=task["phase"],
                    error="后台服务在执行期间停止。已保留分支和日志；请创建新任务。",
                )
                self.event(
                    task["id"],
                    "interrupted",
                    "服务重启，执行中的任务标记为中断；未自动重复模型调用",
                )
