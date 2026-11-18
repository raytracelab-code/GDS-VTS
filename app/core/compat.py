"""Small behavior-preserving Python 3.8 compatibility primitives."""
from concurrent.futures import ThreadPoolExecutor as _ThreadPoolExecutor
from enum import Enum
from pathlib import Path
from threading import RLock
from weakref import WeakSet


class LegacyStrEnum(str, Enum):
    __str__ = str.__str__
    __format__ = str.__format__

    @staticmethod
    def _generate_next_value_(name, start, count, last_values):
        return name.lower()


try:
    from enum import StrEnum
except ImportError:
    StrEnum = LegacyStrEnum


def remove_prefix(value, prefix):
    return value[len(prefix):] if prefix and value.startswith(prefix) else value


def remove_suffix(value, suffix):
    return value[:-len(suffix)] if suffix and value.endswith(suffix) else value


def is_relative_to(path, root):
    try:
        Path(path).relative_to(root)
        return True
    except ValueError:
        return False


class ThreadPoolExecutor(_ThreadPoolExecutor):
    """Public Future.cancel implements cancel_futures on Python 3.8 too."""
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._compat_lock = RLock()
        self._compat_futures = WeakSet()
        self._compat_closing = False

    def submit(self, fn, *args, **kwargs):
        with self._compat_lock:
            if self._compat_closing:
                raise RuntimeError('cannot schedule new futures after shutdown')
            future = super().submit(fn, *args, **kwargs)
            self._compat_futures.add(future)
            return future

    def shutdown(self, wait=True, *, cancel_futures=False):
        with self._compat_lock:
            self._compat_closing = True
            if cancel_futures:
                for future in list(self._compat_futures):
                    future.cancel()
            # Do not hold our lock while joining a worker/callback.
        return super().shutdown(wait=wait)
