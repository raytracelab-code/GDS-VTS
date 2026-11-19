"""Daemon worker pool for abandonable network requests.

concurrent.futures.ThreadPoolExecutor joins its workers at interpreter exit
(non-daemon threads on Python 3.9+, an atexit join on 3.8), so a stalled
remote server could hold the closed application open for the full socket
timeout. Remote provider work is only HTTP plus an atomic cache replace
(temporary file, then os.replace), so it is safe to abandon at shutdown.
Local disk/GIS work keeps using the standard executor.
"""
import queue
import threading
import time
from concurrent.futures import Future


class DaemonExecutor:
    def __init__(self, max_workers=3, thread_name_prefix='daemon-worker'):
        self._max = max(1, int(max_workers))
        self._prefix = thread_name_prefix
        self._queue = queue.Queue()
        self._threads = []
        self._lock = threading.Lock()
        self._closing = False

    def submit(self, fn, *args, **kwargs):
        with self._lock:
            if self._closing:
                raise RuntimeError('cannot schedule new futures after shutdown')
            future = Future()
            self._queue.put((future, fn, args, kwargs))
            if len(self._threads) < self._max:
                thread = threading.Thread(target=self._worker, name=f'{self._prefix}_{len(self._threads)}', daemon=True)
                self._threads.append(thread)
                thread.start()
            return future

    def _worker(self):
        while True:
            item = self._queue.get()
            if item is None:
                return
            future, fn, args, kwargs = item
            if not future.set_running_or_notify_cancel():
                continue
            try:
                result = fn(*args, **kwargs)
            except BaseException as error:  # delivered to the future, as ThreadPoolExecutor does
                future.set_exception(error)
            else:
                future.set_result(result)

    def shutdown(self, wait=True, *, cancel_futures=False, timeout=2.0):
        """Return True when every worker exited; False when in-flight work was abandoned."""
        with self._lock:
            self._closing = True
            if cancel_futures:
                while True:
                    try:
                        item = self._queue.get_nowait()
                    except queue.Empty:
                        break
                    if item is not None:
                        item[0].cancel()
            threads = list(self._threads)
            for _ in threads:
                self._queue.put(None)
        if not wait:
            return not any(t.is_alive() for t in threads)
        deadline = None if timeout is None else time.monotonic() + max(0.0, timeout)
        for thread in threads:
            thread.join(None if deadline is None else max(0.0, deadline - time.monotonic()))
        return not any(t.is_alive() for t in threads)
