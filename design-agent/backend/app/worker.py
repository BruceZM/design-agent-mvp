import threading

from .workflow import Workflow


class Worker:
    def __init__(self, settings, store):
        self.settings, self.store = settings, store
        self.wake = threading.Event()
        self.stop_event = threading.Event()
        self.thread = threading.Thread(
            target=self.loop, name="design-agent-worker", daemon=True
        )

    def start(self):
        self.store.interrupt_running()
        self.thread.start()
        self.wake.set()

    def notify(self):
        self.wake.set()

    def loop(self):
        while not self.stop_event.is_set():
            pending = self.store.pending()
            if pending:
                Workflow(self.settings, self.store, pending[0]).run()
            else:
                self.wake.wait(2)
                self.wake.clear()

    def stop(self):
        self.stop_event.set()
        self.wake.set()
