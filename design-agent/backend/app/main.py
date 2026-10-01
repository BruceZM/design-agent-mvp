import hashlib
import re
import secrets
import shutil
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Annotated

from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, JSONResponse

from .config import Settings
from .documents import IMAGE_LIMIT, PRD_LIMIT, parse_prd, validate_image
from .store import Store
from .worker import Worker

TASK_ID = re.compile(r"^t-[a-f0-9]{12}$")
ARTIFACTS = {
    "report.md",
    "report.json",
    "plan.json",
    "design-spec.md",
    "prd-extracted.md",
    "changes.diff",
    "typecheck.log",
    "build.log",
    "agent-summary.md",
    "verification.md",
}


def create_app(settings=None, start_worker=True):
    settings = settings or Settings()
    settings.runtime.mkdir(parents=True, exist_ok=True)
    store = Store(settings.runtime / "tasks.sqlite3")
    worker = Worker(settings, store)

    @asynccontextmanager
    async def lifespan(app):
        if start_worker:
            worker.start()
        yield
        if start_worker:
            worker.stop()

    app = FastAPI(title="Design Agent 本地 MVP", lifespan=lifespan)
    app.state.store, app.state.settings = store, settings

    @app.middleware("http")
    async def guard_upload(request: Request, call_next):
        if request.method == "POST":
            if request.headers.get("x-design-agent") != "local-mvp":
                return JSONResponse({"detail": "需要本地应用请求标识"}, status_code=403)
            length = request.headers.get("content-length")
            if not length or not length.isdigit():
                return JSONResponse(
                    {"detail": "上传请求必须提供 Content-Length"}, status_code=411
                )
            if int(length) > IMAGE_LIMIT + PRD_LIMIT + 64_000:
                return JSONResponse(
                    {"detail": "上传材料总大小超出限制"}, status_code=413
                )
        return await call_next(request)

    def task_or_404(task_id):
        if not TASK_ID.fullmatch(task_id):
            raise HTTPException(404, "任务不存在")
        task = store.get(task_id)
        if not task:
            raise HTTPException(404, "任务不存在")
        return task

    @app.get("/api/health")
    def health():
        return {
            "status": "ok",
            "target_name": "青禾 CRM",
            "base_branch": "main",
            "model": settings.model,
            "configured": bool(settings.api_key),
            "image_parser": settings.vision_mode,
            "worker": "single serial worker",
        }

    @app.get("/api/tasks")
    def list_tasks():
        return {"tasks": store.list()}

    @app.get("/api/submissions/{key}")
    def submission(key: str):
        task, _ = store.by_key(key)
        if not task:
            raise HTTPException(404, "尚未找到该提交")
        return task

    @app.post("/api/tasks", status_code=202)
    async def submit(
        design: Annotated[UploadFile, File()],
        prd: Annotated[UploadFile, File()],
        instructions: str = Form(""),
        idempotency_key: str = Form(...),
    ):
        if not 8 <= len(idempotency_key) <= 100:
            raise HTTPException(422, "提交标识长度不合法")
        if len(instructions) > 2000:
            raise HTTPException(422, "补充说明最多 2000 字符")
        image = await design.read(IMAGE_LIMIT + 1)
        document = await prd.read(PRD_LIMIT + 1)
        design_name, prd_name = (
            Path(design.filename or "design").name[:200],
            Path(prd.filename or "prd").name[:200],
        )
        try:
            validate_image(image, design_name)
            parse_prd(document, prd_name)
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from exc
        fingerprint = hashlib.sha256(
            image
            + b"\x00"
            + document
            + b"\x00"
            + instructions.encode()
            + b"\x00"
            + prd_name.encode()
        ).hexdigest()
        # Check and insert are atomic against other HTTP requests in this process.
        with store.lock:
            existing, previous = store.by_key(idempotency_key)
            if existing:
                if previous != fingerprint:
                    raise HTTPException(
                        409, "同一提交标识对应的材料已变化，请重新确认后提交"
                    )
                return existing
            if len(store.pending()) >= 10:
                raise HTTPException(429, "本地队列已满，请等待当前任务完成")
            if not settings.api_key:
                raise HTTPException(503, "后端尚未配置模型密钥，材料未创建任务")
            task_id = "t-" + secrets.token_hex(6)
            directory = settings.runtime / "tasks" / task_id
            directory.mkdir(parents=True)
            suffix = Path(design_name).suffix.lower()
            try:
                (directory / ("design" + suffix)).write_bytes(image)
                (directory / "prd").write_bytes(document)
                task = store.create(
                    task_id,
                    idempotency_key,
                    fingerprint,
                    {
                        "design_name": design_name,
                        "design_suffix": suffix,
                        "design_size": len(image),
                        "prd_name": prd_name,
                        "prd_size": len(document),
                        "instructions": instructions,
                        "target_name": "青禾 CRM",
                        "checks": [],
                    },
                )
            except Exception:
                shutil.rmtree(directory)
                raise
        worker.notify()
        return task

    @app.get("/api/tasks/{task_id}")
    def snapshot(task_id: str):
        task = task_or_404(task_id)
        task["events"] = store.events(task_id)
        directory = settings.runtime / "tasks" / task_id
        task["artifacts"] = (
            sorted(p.name for p in directory.iterdir() if p.name in ARTIFACTS)
            if directory.exists()
            else []
        )
        return task

    @app.get("/api/tasks/{task_id}/artifacts/{name}")
    def artifact(task_id: str, name: str):
        task_or_404(task_id)
        path = settings.runtime / "tasks" / task_id / name
        if name not in ARTIFACTS or not path.is_file():
            raise HTTPException(404, "交付文件尚未生成")
        return FileResponse(path, filename=name)

    @app.get("/api/tasks/{task_id}/preview/")
    @app.get("/api/tasks/{task_id}/preview/{asset:path}")
    def preview(task_id: str, asset: str = "index.html"):
        task = task_or_404(task_id)
        if not any(
            c["name"] == "build" and c["status"] == "passed"
            for c in task.get("checks", [])
        ):
            raise HTTPException(409, "此任务还没有可用的构建预览")
        root = (settings.runtime / "worktrees" / task_id / "dist").resolve()
        path = (root / (asset or "index.html")).resolve()
        if not path.is_relative_to(root) or not path.is_file():
            raise HTTPException(404, "预览资源不存在")
        return FileResponse(path, headers={"Cache-Control": "no-store"})

    frontend = settings.root / "frontend/dist"

    @app.get("/{path:path}")
    def frontend_page(path: str):
        if path.startswith("api/"):
            raise HTTPException(404, "接口不存在")
        root = frontend.resolve()
        requested = (root / path).resolve()
        if not requested.is_relative_to(root):
            raise HTTPException(404)
        file = requested if requested.is_file() else root / "index.html"
        if not file.is_file():
            raise HTTPException(
                503, "前端尚未构建，请启动 frontend 或执行 npm run build"
            )
        return FileResponse(file)

    return app


app = create_app()
