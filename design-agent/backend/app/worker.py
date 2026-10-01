# MVP 后台执行器：一个线程串行取 SQLite 队列，无 Redis/Celery 等额外服务。
# HTTP 提交很快返回；长模型任务不占用浏览器请求的生命周期。
import threading

from .workflow import Workflow


class Worker:
    def __init__(self, settings, store):
        self.settings, self.store = settings, store
        self.wake = threading.Event()
        # wake 用于“有新任务”的通知，stop_event 用于退出循环，职责分开。
        self.stop_event = threading.Event()
        self.thread = threading.Thread(
            # daemon 线程不会独自阻止进程退出；这不是持久化任务执行保障。
            target=self.loop, name="design-agent-worker", daemon=True
        )

    def start(self):
        # 重启时旧 running 标记为中断，不自动重放可能已经付费的模型操作。
        # 尚未开始的 queued 仍留在数据库，线程启动后会继续从队列取出。
        self.store.interrupt_running()
        self.thread.start()
        self.wake.set()

    def notify(self):
        # Event 只负责唤醒，任务本身存数据库；多个通知合并也不会丢任务。
        self.wake.set()

    def loop(self):
        while not self.stop_event.is_set():
            pending = self.store.pending()
            if pending:
                # 按创建时间取第一条；run 同步返回后才会开始下一条。
                Workflow(self.settings, self.store, pending[0]).run()
            else:
                # 没任务时最多等待两秒，兼顾唤醒和低频兜底检查，避免空转占 CPU。
                self.wake.wait(2)
                self.wake.clear()

    def stop(self):
        # 标志让循环在下一次判断时退出，并唤醒空闲等待。
        # 它不强制取消已经进入模型请求的任务，也没有线程 join 等待完成。
        self.stop_event.set()
        self.wake.set()
