"""
One thread for everything MLX does.

MLX ties its GPU streams to the thread that created them. The model used to be loaded on one thread and asked questions from
others, which newer MLX refuses ("There is no Stream(gpu, 1) in current thread"). So the model is loaded here and every
generation runs here too; the rest of JARVIS just hands work over and waits for the answer.
"""

from __future__ import annotations

import queue
import threading


class MLXThread:
    def __init__(self):
        self._jobs: queue.Queue = queue.Queue()
        self._thread = None
        self._start_lock = threading.Lock()

    def _ensure(self):
        with self._start_lock:
            if self._thread is None:
                self._thread = threading.Thread(target=self._run, name="mlx-worker", daemon=True)
                self._thread.start()

    def _run(self):
        while True:
            self._jobs.get()()

    def on_worker(self) -> bool:
        return threading.current_thread() is self._thread

    def call(self, fn):
        """Run fn() on the MLX thread and return its result (or raise its error)."""
        if self.on_worker():
            return fn()
        self._ensure()
        box: dict = {}
        done = threading.Event()

        def job():
            try:
                box["value"] = fn()
            except BaseException as e:                     # noqa: BLE001
                box["error"] = e
            done.set()

        self._jobs.put(job)
        done.wait()
        if "error" in box:
            raise box["error"]
        return box.get("value")

    def iterate(self, make_iter, cancel: threading.Event | None = None):
        """Run make_iter() on the MLX thread and yield what it produces, here, in the caller's thread."""
        if self.on_worker():
            yield from make_iter()
            return
        self._ensure()
        out: queue.Queue = queue.Queue(maxsize=256)
        stop = threading.Event()

        def stopped():
            return stop.is_set() or (cancel is not None and cancel.is_set())

        def put(x):                                        # never blocks forever if the caller walked away
            while not stopped():
                try:
                    out.put(x, timeout=0.1)
                    return True
                except queue.Full:
                    pass
            return False

        def job():
            it = None
            try:
                it = make_iter()
                for item in it:
                    if not put(("item", item)):
                        break
                put(("end", None))
            except BaseException as e:                     # noqa: BLE001
                put(("error", e))
            finally:
                close = getattr(it, "close", None)
                if close:
                    try:
                        close()
                    except Exception:                      # noqa: BLE001
                        pass

        self._jobs.put(job)
        try:
            while True:
                try:
                    kind, value = out.get(timeout=0.2)
                except queue.Empty:
                    if cancel is not None and cancel.is_set():
                        return
                    continue
                if kind == "item":
                    if cancel is not None and cancel.is_set():
                        return
                    yield value
                elif kind == "error":
                    raise value
                else:
                    return
        finally:
            stop.set()                                     # the caller stopped early: let the worker move on


MLX = MLXThread()
