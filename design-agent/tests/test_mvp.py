import subprocess
import threading
from io import BytesIO
from types import SimpleNamespace

import pytest
from app.agent import Budget
from app.config import Settings
from app.documents import parse_prd, validate_image
from app.main import create_app
from app.repository import Repository
from app.store import Store
from app.worker import Worker
from app.workflow import Workflow
from docx import Document
from fastapi.testclient import TestClient
from PIL import Image


def image_bytes():
    buf = BytesIO()
    Image.new("RGB", (20, 20), "white").save(buf, format="PNG")
    return buf.getvalue()


@pytest.fixture
def settings(tmp_path):
    target = tmp_path / "crm"
    (target / "src").mkdir(parents=True)
    (target / "node_modules").mkdir()
    (target / "README.md").write_text("React demo rules")
    (target / "src/App.tsx").write_text(
        "export default function App(){return <p>Baseline</p>}"
    )

    def git(*args):
        return subprocess.run(
            ["git", *args], cwd=target, check=True, capture_output=True, text=True
        ).stdout.strip()

    git("init", "-b", "main")
    git("add", "README.md", "src")
    git(
        "-c",
        "user.name=Test",
        "-c",
        "user.email=test@localhost",
        "commit",
        "-m",
        "baseline",
    )
    return Settings(
        root=tmp_path,
        target=target,
        runtime=tmp_path / "runtime",
        api_key="fake-key-tests-only",
    )


def create_task(settings, store, task_id="t-111111111111"):
    directory = settings.runtime / "tasks" / task_id
    directory.mkdir(parents=True)
    (directory / "design.png").write_bytes(image_bytes())
    (directory / "prd").write_text("给客户列表新增筛选。")
    return store.create(
        task_id,
        "key-" + task_id,
        "fingerprint",
        {
            "prd_name": "prd.md",
            "design_name": "design.png",
            "design_suffix": ".png",
            "instructions": "",
            "checks": [],
        },
    )


def test_file_validation_and_parsers():
    validate_image(image_bytes(), "design.png")
    with pytest.raises(ValueError):
        validate_image(b"not an image", "design.png")
    with pytest.raises(ValueError):
        validate_image(image_bytes(), "design.svg")
    assert parse_prd("需求".encode(), "prd.md") == "需求"
    with pytest.raises(ValueError):
        parse_prd(b"", "prd.md")
    with pytest.raises(ValueError):
        parse_prd(b"hello", "prd.exe")
    document = Document()
    document.add_paragraph("新增状态筛选")
    table = document.add_table(rows=1, cols=2)
    table.cell(0, 0).text = "状态"
    table.cell(0, 1).text = "已成交"
    buffer = BytesIO()
    document.save(buffer)
    text = parse_prd(buffer.getvalue(), "prd.docx")
    assert "新增状态筛选" in text and "已成交" in text


def test_upload_idempotency_and_validation(settings):
    app = create_app(settings, start_worker=False)
    with TestClient(app) as client:
        files = {
            "design": ("design.png", image_bytes(), "image/png"),
            "prd": ("prd.md", "需求".encode(), "text/markdown"),
        }
        body = {"idempotency_key": "same-key-123", "instructions": ""}
        assert client.post("/api/tasks", files=files, data=body).status_code == 403
        headers = {"X-Design-Agent": "local-mvp"}
        a = client.post("/api/tasks", headers=headers, files=files, data=body)
        b = client.post("/api/tasks", headers=headers, files=files, data=body)
        assert (
            a.status_code == b.status_code == 202 and a.json()["id"] == b.json()["id"]
        )
        assert len(app.state.store.list()) == 1
        assert (
            client.get("/api/submissions/same-key-123").json()["id"] == a.json()["id"]
        )
        altered = {**body, "instructions": "different"}
        assert (
            client.post(
                "/api/tasks", headers=headers, files=files, data=altered
            ).status_code
            == 409
        )
        bad = {**files, "design": ("design.png", b"invalid", "image/png")}
        assert (
            client.post(
                "/api/tasks",
                headers=headers,
                files=bad,
                data={"idempotency_key": "another-key"},
            ).status_code
            == 422
        )
        assert client.get("/api/tasks/t-111111111111").status_code == 404
        assert (
            client.get(f"/api/tasks/{a.json()['id']}/artifacts/.env").status_code == 404
        )


def test_repository_isolation_and_paths(settings):
    repo = Repository(
        settings.target, settings.runtime / "worktrees" / "t-222222222222"
    )
    before = Repository.command(["git", "rev-parse", "main"], settings.target)
    repo.prepare("t-222222222222")
    assert "node_modules" not in Repository.command(
        ["git", "status", "--porcelain"], repo.worktree
    )
    for path in ["../secrets", ".env", "package.json", "/tmp/no", "src/../../secret"]:
        with pytest.raises(ValueError):
            repo.path(path, write=True)
    (repo.worktree / "src/escape.ts").symlink_to(settings.target / "README.md")
    with pytest.raises(ValueError):
        repo.write("src/escape.ts", "no")
    (repo.worktree / "src/escape.ts").unlink()
    repo.write("src/New.tsx", 'export const label="Feature";')
    diff, files = repo.diff()
    assert "src/New.tsx" in files and "Feature" in diff
    assert not (settings.target / "src/New.tsx").exists()
    assert Repository.command(["git", "rev-parse", "main"], settings.target) == before
    assert (
        Repository.command(
            ["git", "status", "--porcelain", "--untracked-files=no"], settings.target
        )
        == ""
    )


class FakeDeveloper:
    def __init__(self, settings, repo, event):
        self.repo = repo
        self.budget = SimpleNamespace(calls=0, tokens=0)

    def plan(self, prd, design):
        self.budget.calls += 1
        return {
            "summary": "Offline test fixture",
            "files": ["src/App.tsx"],
            "steps": ["edit"],
            "acceptance": ["fixture"],
        }

    def develop(self, *args):
        self.budget.calls += 1
        self.repo.write(
            "src/App.tsx",
            "export default function App(){return <p>Changed in offline test</p>}",
        )
        return "Offline fixture only, no real model call."


async def fake_vision(*args):
    return "Offline visual fixture only."


def test_graph_repairs_and_delivery(settings, monkeypatch):
    store = Store(settings.runtime / "tasks.sqlite3")
    create_task(settings, store)
    counts = {"n": 0}

    def check(self, name):
        counts["n"] += 1
        return {
            "name": name,
            "status": "failed" if counts["n"] == 1 else "passed",
            "output": "offline check fixture",
        }

    monkeypatch.setattr(Repository, "check", check)
    workflow = Workflow(
        settings,
        store,
        "t-111111111111",
        vision=fake_vision,
        developer_factory=FakeDeveloper,
    )
    workflow.run()
    task = store.get("t-111111111111")
    assert task["status"] == "succeeded" and task["report"]["repair_rounds"] == 1
    assert task["report"]["model_calls"] == 3
    assert task["checks"][-1]["status"] == "not_run"
    assert "Baseline" in (settings.target / "src/App.tsx").read_text()
    assert (settings.runtime / "tasks/t-111111111111/changes.diff").is_file()


def test_graph_stops_on_check_failures(settings, monkeypatch):
    store = Store(settings.runtime / "tasks.sqlite3")
    create_task(settings, store)
    monkeypatch.setattr(
        Repository,
        "check",
        lambda self, name: {
            "name": name,
            "status": "failed",
            "output": "fixture fails",
        },
    )
    Workflow(
        settings,
        store,
        "t-111111111111",
        vision=fake_vision,
        developer_factory=FakeDeveloper,
    ).run()
    task = store.get("t-111111111111")
    assert task["status"] == "failed" and task["report"]["repair_rounds"] == 1
    assert task["report"]["changed_files"] == ["src/App.tsx"]


def test_vision_failure_and_restart_are_honest(settings):
    store = Store(settings.runtime / "tasks.sqlite3")
    create_task(settings, store)

    async def failure(*args):
        raise RuntimeError("vision denied")

    Workflow(
        settings,
        store,
        "t-111111111111",
        vision=failure,
        developer_factory=FakeDeveloper,
    ).run()
    assert store.get("t-111111111111")["status"] == "failed"
    assert "vision denied" in store.get("t-111111111111")["error"]
    store.update("t-111111111111", status="running", branch="preserved")
    store.interrupt_running()
    task = store.get("t-111111111111")
    assert task["phase"] == "interrupted" and task["branch"] == "preserved"


def test_call_budget_and_redaction(settings):
    settings.max_model_calls = 2
    budget = Budget(settings)
    budget.consume()
    budget.consume()
    with pytest.raises(RuntimeError):
        budget.consume()
    assert settings.api_key not in settings.redact("failure " + settings.api_key)


def test_worker_runs_without_browser_and_serializes_tasks(settings, monkeypatch):
    store = Store(settings.runtime / "tasks.sqlite3")
    create_task(settings, store)
    create_task(settings, store, "t-333333333333")
    first_started, release, finished = (
        threading.Event(),
        threading.Event(),
        threading.Event(),
    )
    starts = []

    class ControlledWorkflow:
        def __init__(self, config, database, task_id):
            self.store, self.task_id = database, task_id

        def run(self):
            starts.append(self.task_id)
            self.store.update(self.task_id, status="running", phase="develop")
            first_started.set()
            assert release.wait(2)
            self.store.update(self.task_id, status="succeeded", phase="completed")
            if len(starts) == 2:
                finished.set()

    monkeypatch.setattr("app.worker.Workflow", ControlledWorkflow)
    worker = Worker(settings, store)
    try:
        worker.start()
        assert first_started.wait(2)
        assert len(starts) == 1
        assert store.get("t-333333333333")["status"] == "queued"
        # No browser or polling request participates in executing either task.
        release.set()
        assert finished.wait(2)
        assert all(task["status"] == "succeeded" for task in store.list())
    finally:
        release.set()
        worker.stop()
        worker.thread.join(timeout=2)
