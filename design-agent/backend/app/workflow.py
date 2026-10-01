import asyncio
import json
from typing import TypedDict

from langgraph.graph import END, START, StateGraph

from .agent import Developer
from .config import Settings
from .documents import parse_prd
from .repository import Repository
from .store import Store
from .vision import describe_image


class State(TypedDict, total=False):
    prd: str
    design_spec: str
    plan: dict
    checks: list[dict]
    attempt: int
    summary: str


class Workflow:
    def __init__(
        self,
        settings: Settings,
        store: Store,
        task_id: str,
        vision=describe_image,
        developer_factory=Developer,
    ):
        self.settings, self.store, self.task_id = settings, store, task_id
        self.task = store.get(task_id)
        self.directory = settings.runtime / "tasks" / task_id
        self.repo = Repository(
            settings.target, settings.runtime / "worktrees" / task_id, self.event
        )
        self.vision, self.developer_factory = vision, developer_factory
        self.developer = None

    def event(self, phase, message):
        self.store.event(self.task_id, phase, self.settings.redact(message))

    def stage(self, phase, message):
        self.store.update(self.task_id, status="running", phase=phase)
        self.event(phase, message)

    def artifact(self, name, text):
        (self.directory / name).write_text(self.settings.redact(text))

    def materials(self, state):
        self.stage("materials", f"解析 PRD，图片解析方式：{self.settings.vision_mode}")
        self.store.update(self.task_id, image_parser=self.settings.vision_mode)
        prd = parse_prd((self.directory / "prd").read_bytes(), self.task["prd_name"])
        if self.task.get("instructions"):
            prd += "\n\n用户补充说明：\n" + self.task["instructions"]
        design = asyncio.run(
            self.vision(
                self.settings, self.directory / ("design" + self.task["design_suffix"])
            )
        )
        self.artifact("design-spec.md", design)
        self.artifact("prd-extracted.md", prd)
        self.event("materials", "PRD 与设计规范已解析，原始文件已保留")
        return {"prd": prd, "design_spec": design, "attempt": 0}

    def prepare(self, state):
        self.stage("prepare", "从固定 main 基线创建独立分支与 worktree")
        metadata = self.repo.prepare(self.task_id)
        self.store.update(self.task_id, **metadata)
        self.event("prepare", f"分支 {metadata['branch']} 已建立")
        self.developer = self.developer_factory(self.settings, self.repo, self.event)
        return {}

    def plan(self, state):
        self.stage("plan", "读取仓库规范，生成受约束的开发计划")
        plan = self.developer.plan(state["prd"], state["design_spec"])
        self.artifact("plan.json", json.dumps(plan, ensure_ascii=False, indent=2))
        self.store.update(self.task_id, plan=plan)
        self.event("plan", plan["summary"])
        return {"plan": plan}

    def develop(self, state):
        attempt = state.get("attempt", 0)
        self.stage(
            "develop",
            "使用工具修改前端源码" if not attempt else f"修复第 {attempt} 轮检查失败",
        )
        repair = "\n".join(
            f"{c['name']}\n{c['output']}"
            for c in state.get("checks", [])
            if c["status"] == "failed"
        )
        summary = self.developer.develop(
            state["prd"], state["design_spec"], state["plan"], repair
        )
        self.artifact("agent-summary.md", summary)
        return {"summary": summary}

    def check(self, state):
        self.stage("checks", "独立执行 TypeScript 与生产构建检查")
        checks = []
        for name in ["typecheck", "build"]:
            result = self.repo.check(name)
            checks.append(result)
            self.event("checks", f"{name}: {result['status']}")
            self.artifact(f"{name}.log", result["output"])
        self.store.update(self.task_id, checks=checks)
        return {"checks": checks, "attempt": state.get("attempt", 0) + 1}

    def route_checks(self, state):
        if all(c["status"] == "passed" for c in state["checks"]):
            return "deliver"
        if state["attempt"] <= self.settings.max_repairs:
            return "develop"
        return "deliver"

    def deliver(self, state):
        self.stage("deliver", "保存代码差异、检查日志与本地交付报告")
        diff, files = self.repo.diff()
        self.artifact("changes.diff", diff)
        checks = state["checks"] + [
            {
                "name": "browser_functional",
                "status": "not_run",
                "output": "自动工作流未执行浏览器验收，需要在交付预览中检查需求行为",
            },
            {
                "name": "visual_review",
                "status": "not_run",
                "output": "未执行自动视觉比对，编译通过不等于 UI 一致",
            },
        ]
        passed = all(c["status"] == "passed" for c in state["checks"])
        if not files:
            passed = False
        if passed:
            self.repo.commit(self.task_id)
        task = self.store.get(self.task_id)
        report = {
            "task_id": self.task_id,
            "status": "succeeded" if passed else "failed",
            "branch": task["branch"],
            "base_commit": task["base_commit"],
            "worktree": str(self.repo.worktree),
            "changed_files": files,
            "checks": checks,
            "model_calls": self.developer.budget.calls,
            "total_tokens": self.developer.budget.tokens,
            "repair_rounds": max(0, state["attempt"] - 1),
            "summary": state["summary"],
            "remote_pushed": False,
            "image_parser": self.settings.vision_mode,
            "preview_url": f"/api/tasks/{self.task_id}/preview/",
            "limitation": "本地 MVP：交付成功表示代码有修改且编译/构建通过；功能及视觉需单独验收。",
        }
        self.artifact("report.json", json.dumps(report, ensure_ascii=False, indent=2))
        text = (
            f"# Design Agent 交付\n\n任务：{self.task_id}\n\n分支：{task['branch']}\n\n状态：{report['status']}\n\n图片解析：{self.settings.vision_mode}\n\n{state['summary']}\n\n## 检查\n"
            + "\n".join(f"- {c['name']}: {c['status']}" for c in checks)
            + "\n\n"
            + report["limitation"]
        )
        self.artifact("report.md", text)
        self.store.update(
            self.task_id,
            status=report["status"],
            phase="completed" if passed else "checks_failed",
            report=report,
            checks=checks,
            error=None
            if passed
            else ("没有产生源代码修改" if not files else "检查失败，修复次数已用完"),
        )
        self.event(
            "completed" if passed else "checks_failed",
            "本地交付已保存" if passed else "已保留失败分支与报告",
        )
        return {}

    def run(self):
        graph = StateGraph(State)
        for name in ["materials", "prepare", "plan", "develop", "check", "deliver"]:
            graph.add_node(name, getattr(self, name))
        graph.add_edge(START, "materials")
        graph.add_edge("materials", "prepare")
        graph.add_edge("prepare", "plan")
        graph.add_edge("plan", "develop")
        graph.add_edge("develop", "check")
        graph.add_conditional_edges(
            "check", self.route_checks, {"develop": "develop", "deliver": "deliver"}
        )
        graph.add_edge("deliver", END)
        try:
            graph.compile().invoke({}, {"recursion_limit": 25})
        except Exception as exc:  # noqa: BLE001 -- task boundary persists all failures
            error = self.settings.redact(f"{type(exc).__name__}: {exc}")[:3000]
            # Preserve useful code on interrupted model/check calls, without committing failures.
            if self.repo.worktree.exists():
                try:
                    diff, files = self.repo.diff()
                    self.artifact("changes.diff", diff)
                    self.store.update(self.task_id, changed_files=files)
                except Exception as artifact_error:  # noqa: BLE001 -- keep original failure
                    self.event("delivery_warning", f"保存差异失败：{artifact_error}")
            report = {
                "task_id": self.task_id,
                "status": "failed",
                "error": error,
                "checks": self.store.get(self.task_id).get("checks", []),
                "model_calls": self.developer.budget.calls if self.developer else 0,
            }
            self.artifact(
                "report.json", json.dumps(report, ensure_ascii=False, indent=2)
            )
            self.artifact(
                "report.md",
                f"# 任务失败\n\n{error}\n\n已有材料、分支与日志已保留；未自动重新提交任务。",
            )
            self.store.update(self.task_id, status="failed", error=error, report=report)
            self.event("failed", error)
