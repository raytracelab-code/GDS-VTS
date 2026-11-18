from __future__ import annotations
from abc import ABC, abstractmethod
from typing import Callable


class BaseTransport(ABC):
    """Transport abstraction: implementations emit bytes, never parsed frames."""
    def __init__(self) -> None:
        self.on_data: Callable[[bytes], None] | None = None
        self.on_state: Callable[[bool], None] | None = None
        self.on_error: Callable[[str], None] | None = None

    @abstractmethod
    def scan(self): ...
    @abstractmethod
    def connect(self, device): ...
    @abstractmethod
    def disconnect(self) -> None: ...
    @abstractmethod
    def is_connected(self) -> bool: ...
    def start(self) -> None: pass
    def stop(self) -> None: self.disconnect()

    def _emit_error(self, message: str) -> None:
        if self.on_error: self.on_error(message)
