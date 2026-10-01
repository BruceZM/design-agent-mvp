# 一条后台任务的总编排：六个显式阶段 + 检查失败时的有限修复分支。
# SQLite 保存网页可见的任务快照；State 保存本次图执行中节点共享的数据。
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
    # TypedDict 提供字段类型提示；total=False 允许节点执行前尚无对应字段。
    # 节点返回部分字典，LangGraph 将它合并到当前 State，不必重复返回整个状态。
    # 这里没有配置 checkpointer，进程重启后不能从某个节点继续执行。
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
        # 视觉函数和开发者工厂可注入，测试能替换模型而走真实图和 Git 流程。
        self.settings, self.store, self.task_id = settings, store, task_id
        self.task = store.get(task_id)
        self.directory = settings.runtime / "tasks" / task_id
        self.repo = Repository(
            settings.target, settings.runtime / "worktrees" / task_id, self.event
        )
        self.vision, self.developer_factory = vision, developer_factory
        self.developer = None

    def event(self, phase, message):
        # 日志写 SQLite；前端只轮询读取，不直接接收模型的推理文本。
        self.store.event(self.task_id, phase, self.settings.redact(message))

    def stage(self, phase, message):
        # status 是整体状态，phase 是当前阶段：二者不能混成一个字段。
        self.store.update(self.task_id, status="running", phase=phase)
        self.event(phase, message)

    def artifact(self, name, text):
        # 阶段产物落入任务目录，下载接口另外用文件名白名单控制访问。
        (self.directory / name).write_text(self.settings.redact(text))

    def materials(self, state):
        # 原始材料已在 HTTP 提交时保存；后台重读并加入用户补充说明。
        self.stage("materials", f"解析 PRD，图片解析方式：{self.settings.vision_mode}")
        self.store.update(self.task_id, image_parser=self.settings.vision_mode)
        prd = parse_prd((self.directory / "prd").read_bytes(), self.task["prd_name"])
        if self.task.get("instructions"):
            prd += "\n\n用户补充说明：\n" + self.task["instructions"]
        design = asyncio.run(
            # Worker 在普通线程中同步跑图，该线程没有正在运行的事件循环。
            # asyncio.run 在此建立临时循环，等待异步识图完成后再进入 prepare。
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
        # Developer 此时才建立：其预算计时不覆盖前面的视觉和仓库准备阶段。
        return {}

    def plan(self, state):
        # 一份计划既写文件方便审阅，又写快照供任务页面直接展示。
        self.stage("plan", "读取仓库规范，生成受约束的开发计划")
        plan = self.developer.plan(state["prd"], state["design_spec"])
        self.artifact("plan.json", json.dumps(plan, ensure_ascii=False, indent=2))
        self.store.update(self.task_id, plan=plan)
        self.event("plan", plan["summary"])
        return {"plan": plan}

    def develop(self, state):
        # attempt 表示已经执行的独立检查轮数；0 是首次开发。
        # 修复时继续使用同一分支和 Developer，不重新计划，也不重置预算。
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
        # 不相信模型摘要中的“检查通过”：由工作流独立执行两项命令。
        # 第一项失败也会运行第二项，得到完整反馈；每一轮都会覆盖对应日志文件。
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
        # 首次检查后 attempt=1，max_repairs=1 允许回到 develop 一次。
        # 第二次仍失败时 attempt=2，进入 deliver 保存失败报告，而非无限重试。
        if all(c["status"] == "passed" for c in state["checks"]):
            return "deliver"
        if state["attempt"] <= self.settings.max_repairs:
            return "develop"
        return "deliver"

    def deliver(self, state):
        # diff() 会暂存允许的源码改动；通过编译/构建且有改动才真正 commit。
        # 两种结果都保存差异和报告，失败时保留工作目录便于排查。
        self.stage("deliver", "保存代码差异、检查日志与本地交付报告")
        diff, files = self.repo.diff()
        self.artifact("changes.diff", diff)
        checks = state["checks"] + [
            # not_run 是未验收，不是通过。MVP 没有自动浏览器测试和视觉比对。
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
            # model_calls / total_tokens 只来自 Developer，不包含前面的视觉调用。
            # 生成 preview_url 不代表预览一定可用，API 仍检查 build 是否 passed。
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
        # 节点名称映射到同名实例方法，便于把流程图直接对应到代码。
        # START/END 是 LangGraph 的边界标记，不是需要自己实现的业务节点。
        graph = StateGraph(State)
        for name in ["materials", "prepare", "plan", "develop", "check", "deliver"]:
            graph.add_node(name, getattr(self, name))
        graph.add_edge(START, "materials")
        graph.add_edge("materials", "prepare")
        graph.add_edge("prepare", "plan")
        graph.add_edge("plan", "develop")
        graph.add_edge("develop", "check")
        graph.add_conditional_edges(
            # 路由函数返回逻辑标签，映射表将标签解析为下一节点名称。
            "check", self.route_checks, {"develop": "develop", "deliver": "deliver"}
        )
        graph.add_edge("deliver", END)
        try:
            # compile 构建可执行图；invoke 同步运行到结束，Worker 随后处理下一条。
            # 25 限制外层图步数；内部编码 Agent 有自己的 45 步限制和模型预算。
            graph.compile().invoke({}, {"recursion_limit": 25})
        except Exception as exc:  # noqa: BLE001 -- task boundary persists all failures
            error = self.settings.redact(f"{type(exc).__name__}: {exc}")[:3000]
            # 这是任务边界的兜底捕获：将模型、工具、Git 等异常转成可查询的失败。
            # 保存已有代码差异，避免用户只看到报错却丢失排查材料；失败不提交。
            if self.repo.worktree.exists():
                try:
                    diff, files = self.repo.diff()
                    self.artifact("changes.diff", diff)
                    self.store.update(self.task_id, changed_files=files)
                except Exception as artifact_error:  # noqa: BLE001 -- keep original failure
                    # 保存差异再失败时，仅追加警告，不覆盖导致任务失败的原始异常。
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
