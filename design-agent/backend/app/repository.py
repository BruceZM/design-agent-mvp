# 模型与文件系统之间的执行边界：Git 隔离、路径白名单、固定检查和本地提交。
# 这些检查是代码约束；不能仅依靠提示词要求模型“不要越权”。
import os
import subprocess
import time
from pathlib import Path


class Repository:
    def __init__(self, target: Path, worktree: Path, event=lambda *_: None):
        self.target = target.resolve()
        self.worktree = worktree
        self.event = event

    @staticmethod
    def command(args, cwd, timeout=60):
        # 参数数组直接启动子进程，不经 shell 拼接；禁止 Git 弹出交互登录。
        # 失败时抛异常，避免把失败的 Git 命令当成已完成步骤。
        result = subprocess.run(
            args,
            cwd=cwd,
            capture_output=True,
            check=False,
            text=True,
            timeout=timeout,
            env={**os.environ, "GIT_TERMINAL_PROMPT": "0"},
        )
        if result.returncode:
            raise RuntimeError(
                f"{args[0]} 操作失败：{(result.stderr or result.stdout)[-2500:]}"
            )
        return result.stdout.strip()

    def prepare(self, task_id):
        # 每个任务从固定 main 提交创建独立分支/worktree，主目录不会被模型改动。
        # worktree 是同一 Git 仓库的额外工作目录，不是重新下载一个完整仓库。
        if not (self.target / ".git").exists():
            raise RuntimeError("固定客户仓库尚未初始化 Git")
        base = self.command(["git", "rev-parse", "main"], self.target)
        branch = f"design-agent/{task_id}"
        self.worktree.parent.mkdir(parents=True, exist_ok=True)
        self.command(
            ["git", "worktree", "add", "-b", branch, str(self.worktree), base],
            self.target,
        )
        # 依赖由使用者预先安装，工作目录复用它，模型没有安装新依赖的工具。
        if not (self.target / "node_modules").is_dir():
            raise RuntimeError("请先在客户仓库执行 npm ci")
        (self.worktree / "node_modules").symlink_to(
            self.target / "node_modules", target_is_directory=True
        )
        # /node_modules/ 只匹配真实目录，无法忽略这个符号链接。
        # 使用本地 info/exclude 忽略链接，不把依赖连接写入需求源码差异。
        exclude = Path(
            self.command(
                ["git", "rev-parse", "--git-path", "info/exclude"], self.worktree
            )
        )
        if not exclude.is_absolute():
            exclude = self.worktree / exclude
        existing = exclude.read_text() if exclude.exists() else ""
        if "/node_modules" not in existing.splitlines():
            exclude.parent.mkdir(parents=True, exist_ok=True)
            exclude.write_text(existing + "\n/node_modules\n")
        return {"branch": branch, "base_commit": base, "worktree": str(self.worktree)}

    def path(self, relative: str, write=False):
        # 一层检查输入语法与权限，另一层 resolve 后确认实际路径仍在 worktree。
        # 即使路径看似 src/x，也可能通过符号链接指向 .env 或其他目录。
        candidate = Path(relative)
        if candidate.is_absolute() or ".." in candidate.parts:
            raise ValueError("只允许仓库内相对路径")
        if write:
            if (
                not candidate.parts
                or candidate.parts[0] != "src"
                or candidate.suffix not in {".ts", ".tsx", ".css"}
            ):
                raise ValueError("MVP 仅允许修改 src/ 中的 TS、TSX、CSS")
        elif str(candidate) != "README.md" and (
            not candidate.parts or candidate.parts[0] != "src"
        ):
            raise ValueError("仅允许读取 README.md 与 src/")
        resolved = (self.worktree / candidate).resolve()
        if not resolved.is_relative_to(self.worktree.resolve()):
            raise ValueError("禁止通过符号链接访问仓库外文件")
        for parent in [self.worktree / candidate, *(self.worktree / candidate).parents]:
            # 不只拒绝最终文件链接，还拒绝任何中间目录链接。
            if parent == self.worktree:
                break
            if parent.is_symlink():
                raise ValueError("禁止读写符号链接")
        return resolved

    def files(self):
        # sorted 保证提示词中的文件顺序稳定；只列出许可的前端源码和 README。
        return ["README.md"] + [
            str(p.relative_to(self.worktree))
            for p in sorted((self.worktree / "src").rglob("*"))
            if p.is_file()
            and not p.is_symlink()
            and p.suffix in {".ts", ".tsx", ".css"}
        ]

    def read(self, relative):
        # 大文件限制避免一次读入占满模型上下文；每次读取都重新校验路径。
        path = self.path(relative)
        if path.stat().st_size > 80_000:
            raise ValueError("单文件超过读取限制")
        return path.read_text()

    def write(self, relative, content):
        # 按编码后字节数限制，而不是字符数；自动创建新增文件所需目录。
        if len(content.encode()) > 80_000:
            raise ValueError("单文件超过 80 KB 限制")
        path = self.path(relative, write=True)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)
        self.event("develop", f"已写入 {relative}")

    def check(self, name):
        # name 只能命中两个已知 npm 脚本，模型不能传入任意命令。
        # 非零退出和超时都返回结构化 failed，供 workflow 判断是否需要修复。
        if name not in {"typecheck", "build"}:
            raise ValueError("仅允许 typecheck 或 build")
        start = time.monotonic()
        try:
            p = subprocess.run(
                ["npm", "run", name],
                cwd=self.worktree,
                capture_output=True,
                check=False,
                text=True,
                timeout=100,
            )
            return {
                "name": name,
                "status": "passed" if p.returncode == 0 else "failed",
                "duration_seconds": round(time.monotonic() - start, 2),
                "output": (p.stdout + "\n" + p.stderr)[-7000:],
            }
        except subprocess.TimeoutExpired:
            return {
                "name": name,
                "status": "failed",
                "duration_seconds": 100,
                "output": "检查执行超时",
            }

    def diff(self):
        # 先暂存 src/，再读 cached diff，才能把未跟踪的新文件也纳入交付。
        # 这是本地暂存，不是提交；提交必须等 workflow 的检查门槛通过。
        self.command(["git", "add", "--", "src"], self.worktree)
        files = self.command(
            ["git", "diff", "--cached", "--name-only"], self.worktree
        ).splitlines()
        if any(not f.startswith("src/") for f in files):
            raise RuntimeError("发现许可范围之外的修改")
        return self.command(
            ["git", "diff", "--cached", "--no-ext-diff"], self.worktree
        ), files

    def commit(self, task_id):
        # 作者只针对本次命令设置，不更改使用者全局 Git 配置。
        # hooksPath 禁用本次提交钩子；该方法不会向远程仓库 push。
        return self.command(
            [
                "git",
                "-c",
                "user.name=Design Agent",
                "-c",
                "user.email=design-agent@localhost",
                "-c",
                "core.hooksPath=/dev/null",
                "commit",
                "-m",
                f"Implement task {task_id}",
            ],
            self.worktree,
        )
