import json
import sqlite3
import threading
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path


def now() -> str:
    return datetime.now(UTC).isoformat()


class Store:
    def __init__(self, path: Path):
        path.parent.mkdir(parents=True, exist_ok=True)
        self.path = path
        self.lock = threading.RLock()
        with self.connect() as db:
            db.executescript("""PRAGMA journal_mode=WAL;
            CREATE TABLE IF NOT EXISTS tasks (id TEXT PRIMARY KEY, key TEXT UNIQUE NOT NULL, fingerprint TEXT NOT NULL, status TEXT NOT NULL, phase TEXT NOT NULL, created_at TEXT NOT NULL, updated_at TEXT NOT NULL, revision INTEGER NOT NULL, data TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS events (task_id TEXT NOT NULL, seq INTEGER NOT NULL, at TEXT NOT NULL, phase TEXT NOT NULL, message TEXT NOT NULL, PRIMARY KEY(task_id,seq));""")

    @contextmanager
    def connect(self):
        db = sqlite3.connect(self.path, timeout=10)
        db.row_factory = sqlite3.Row
        try:
            with db:
                yield db
        finally:
            db.close()

    @staticmethod
    def decode(row):
        if row is None:
            return None
        task = dict(row)
        task.update(json.loads(task.pop("data")))
        task.pop("key", None)
        task.pop("fingerprint", None)
        return task

    def get(self, task_id):
        with self.connect() as db:
            return self.decode(
                db.execute("SELECT * FROM tasks WHERE id=?", (task_id,)).fetchone()
            )

    def by_key(self, key):
        with self.connect() as db:
            row = db.execute("SELECT * FROM tasks WHERE key=?", (key,)).fetchone()
            return (self.decode(row), row["fingerprint"]) if row else (None, None)

    def create(self, task_id, key, fingerprint, data):
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
        with self.connect() as db:
            return [
                dict(r)
                for r in db.execute(
                    "SELECT * FROM events WHERE task_id=? ORDER BY seq", (task_id,)
                )
            ]

    def list(self):
        with self.connect() as db:
            return [
                self.decode(r)
                for r in db.execute(
                    "SELECT * FROM tasks ORDER BY created_at DESC LIMIT 50"
                )
            ]

    def pending(self):
        with self.connect() as db:
            return [
                r["id"]
                for r in db.execute(
                    "SELECT id FROM tasks WHERE status='queued' ORDER BY created_at"
                )
            ]

    def interrupt_running(self):
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
