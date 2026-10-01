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
        if not (self.target / ".git").exists():
            raise RuntimeError("固定客户仓库尚未初始化 Git")
        base = self.command(["git", "rev-parse", "main"], self.target)
        branch = f"design-agent/{task_id}"
        self.worktree.parent.mkdir(parents=True, exist_ok=True)
        self.command(
            ["git", "worktree", "add", "-b", branch, str(self.worktree), base],
            self.target,
        )
        # Dependencies are installed by the owner, outside model-controlled paths.
        if not (self.target / "node_modules").is_dir():
            raise RuntimeError("请先在客户仓库执行 npm ci")
        (self.worktree / "node_modules").symlink_to(
            self.target / "node_modules", target_is_directory=True
        )
        # A trailing-slash ignore only matches real directories, not this symlink.
        # Keep dependency wiring in local Git metadata, outside the source diff.
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
            if parent == self.worktree:
                break
            if parent.is_symlink():
                raise ValueError("禁止读写符号链接")
        return resolved

    def files(self):
        return ["README.md"] + [
            str(p.relative_to(self.worktree))
            for p in sorted((self.worktree / "src").rglob("*"))
            if p.is_file()
            and not p.is_symlink()
            and p.suffix in {".ts", ".tsx", ".css"}
        ]

    def read(self, relative):
        path = self.path(relative)
        if path.stat().st_size > 80_000:
            raise ValueError("单文件超过读取限制")
        return path.read_text()

    def write(self, relative, content):
        if len(content.encode()) > 80_000:
            raise ValueError("单文件超过 80 KB 限制")
        path = self.path(relative, write=True)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)
        self.event("develop", f"已写入 {relative}")

    def check(self, name):
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
        # Stage only allowed source changes to include newly created files in the diff.
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
