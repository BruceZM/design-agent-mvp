# HTTP 入口：接收上传、返回任务快照、提供产物和构建预览。
# 长任务委托 Worker；本文件不直接等待 GLM 完成开发。
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
# 明确列举可下载产物，不能让任意文件名暴露本地 .env 或其他文件。
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
    # 应用工厂使测试可注入临时配置并关闭 Worker；生产入口使用末尾的 app。
    settings = settings or Settings()
    settings.runtime.mkdir(parents=True, exist_ok=True)
    store = Store(settings.runtime / "tasks.sqlite3")
    worker = Worker(settings, store)

    @asynccontextmanager
    async def lifespan(app):
        # 启动/关闭操作绑定服务生命周期，导入模块时不会直接启动后台线程。
        if start_worker:
            worker.start()
        yield
        if start_worker:
            worker.stop()

    app = FastAPI(title="Design Agent 本地 MVP", lifespan=lifespan)
    app.state.store, app.state.settings = store, settings

    @app.middleware("http")
    async def guard_upload(request: Request, call_next):
        # 先限制整个请求，再在 submit 中分别限制两个文件。
        # 自定义头仅降低普通网页跨来源误提交风险，不是登录鉴权或完整安全沙箱。
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
        # 在拼接任务文件路径之前检查 ID 格式；重复查询逻辑集中在一个帮助函数。
        if not TASK_ID.fullmatch(task_id):
            raise HTTPException(404, "任务不存在")
        task = store.get(task_id)
        if not task:
            raise HTTPException(404, "任务不存在")
        return task

    @app.get("/api/health")
    def health():
        # 网页只需要“是否配置”，绝不能把 API key 返回浏览器。
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
        # 上传响应丢失时可按原提交 key 找回任务，避免用户再次启动同一长任务。
        task, _ = store.by_key(key)
        if not task:
            raise HTTPException(404, "尚未找到该提交")
        return task

    @app.post("/api/tasks", status_code=202)
    async def submit(
        # Annotated 的 File/Form 声明告诉 FastAPI 从 multipart 的哪个部分取值。
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
        # 多读 1 字节用于识别超限，避免无上限地把整个文件读入内存。
        document = await prd.read(PRD_LIMIT + 1)
        design_name, prd_name = (
            # 原文件名仅作显示和格式判断，实际保存使用固定名称；丢弃上传路径。
            Path(design.filename or "design").name[:200],
            Path(prd.filename or "prd").name[:200],
        )
        try:
            validate_image(image, design_name)
            parse_prd(document, prd_name)
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from exc
        fingerprint = hashlib.sha256(
            # 指纹代表材料内容，key 代表一次提交意图；二者配合识别安全重试。
            # NUL 分隔各部分，PRD 文件名影响解析类型，也纳入指纹。
            image
            + b"\x00"
            + document
            + b"\x00"
            + instructions.encode()
            + b"\x00"
            + prd_name.encode()
        ).hexdigest()
        # 锁住查询与创建整段，避免并发重试同时通过“还没任务”的判断。
        # 这段原子性只覆盖本进程；MVP 按单 API 进程 + 单 Worker 运行。
        with store.lock:
            existing, previous = store.by_key(idempotency_key)
            if existing:
                # 相同 key + 相同材料直接返回原任务；改变材料用同 key 会返回 409。
                if previous != fingerprint:
                    raise HTTPException(
                        409, "同一提交标识对应的材料已变化，请重新确认后提交"
                    )
                return existing
            if len(store.pending()) >= 10:
                # 限制排队数，不把唯一正在运行的任务计算在 queued 数量里。
                raise HTTPException(429, "本地队列已满，请等待当前任务完成")
            if not settings.api_key:
                raise HTTPException(503, "后端尚未配置模型密钥，材料未创建任务")
            task_id = "t-" + secrets.token_hex(6)
            directory = settings.runtime / "tasks" / task_id
            directory.mkdir(parents=True)
            suffix = Path(design_name).suffix.lower()
            try:
                # 先保存完整材料再提交任务行，Worker 才能按 ID 读取材料。
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
                # 只清理本次新建但未成功创建任务的目录，已有任务不会被删除。
                shutil.rmtree(directory)
                raise
        worker.notify()
        # 创建已持久化才唤醒后台；202 表示已接收，并不表示代码已开发完成。
        return task

    @app.get("/api/tasks/{task_id}")
    def snapshot(task_id: str):
        # 每次返回最新快照、完整事件和已落盘白名单产物，前端据此显示下载按钮。
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
        # FileResponse 流式发送现有文件，不把报告内容重新编码成 JSON。
        task_or_404(task_id)
        path = settings.runtime / "tasks" / task_id / name
        if name not in ARTIFACTS or not path.is_file():
            raise HTTPException(404, "交付文件尚未生成")
        return FileResponse(path, filename=name)

    @app.get("/api/tasks/{task_id}/preview/")
    @app.get("/api/tasks/{task_id}/preview/{asset:path}")
    def preview(task_id: str, asset: str = "index.html"):
        # 预览必须有 build passed；失败任务若 build 单项通过也可提供构建预览。
        # resolve 后再检查边界，禁止通过 ../ 或符号链接取 dist 以外的资源。
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
        # API 路由先注册，最后兜底前端静态资源和 SPA 页面刷新。
        # 找不到前端路径时回 index.html，让客户端 usePath 决定展示哪个页面。
        # 未知 api/ 路径明确 404，不能误返回 HTML 让前端当 JSON 解析。
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


# uvicorn 使用 app.main:app 导入这里；启动 Worker 要等 lifespan 进入。
app = create_app()
