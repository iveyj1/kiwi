"""Background operation worker for interactive client/TUI use."""

from __future__ import annotations

import queue
import threading
import time
from dataclasses import dataclass
from typing import Callable


@dataclass(frozen=True)
class OperationStatus:
    """Snapshot of a background operation."""

    name: str | None
    running: bool
    stop_requested: bool
    started_at: float | None
    finished_at: float | None
    result: dict | None
    error: str | None

    @property
    def elapsed_seconds(self) -> float:
        if self.started_at is None:
            return 0.0
        end = time.monotonic() if self.finished_at is None else self.finished_at
        return max(0.0, end - self.started_at)

    def as_dict(self) -> dict:
        return {
            "name": self.name,
            "running": self.running,
            "stop_requested": self.stop_requested,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "elapsed_seconds": self.elapsed_seconds,
            "result": self.result,
            "error": self.error,
        }


class BackgroundOperation:
    """Run at most one cooperative background operation."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._thread: threading.Thread | None = None
        self._stop_event = threading.Event()
        self._command_queue: queue.Queue[str] = queue.Queue()
        self._name: str | None = None
        self._started_at: float | None = None
        self._finished_at: float | None = None
        self._result: dict | None = None
        self._error: str | None = None

    def start(self, name: str, target: Callable[[threading.Event, queue.Queue[str]], dict]) -> OperationStatus:
        """Start an operation in the background."""
        with self._lock:
            if self._thread is not None and self._thread.is_alive():
                raise RuntimeError("background operation already running")
            self._stop_event = threading.Event()
            self._command_queue = queue.Queue()
            self._name = name
            self._started_at = time.monotonic()
            self._finished_at = None
            self._result = None
            self._error = None
            self._thread = threading.Thread(target=self._run, args=(target,), daemon=True)
            self._thread.start()
            return self.status()

    def stop(self) -> OperationStatus:
        """Request cooperative stop."""
        self._stop_event.set()
        return self.status()

    def send_command(self, command: str) -> OperationStatus:
        """Queue a command for the active background operation."""
        status = self.status()
        if not status.running:
            raise RuntimeError("no background operation running")
        self._command_queue.put(command)
        return self.status()

    def status(self) -> OperationStatus:
        """Return a current operation status snapshot."""
        thread = self._thread
        running = thread is not None and thread.is_alive()
        return OperationStatus(
            name=self._name,
            running=running,
            stop_requested=self._stop_event.is_set(),
            started_at=self._started_at,
            finished_at=self._finished_at,
            result=self._result,
            error=self._error,
        )

    def join(self, timeout: float | None = None) -> OperationStatus:
        """Join the current worker thread, if any."""
        thread = self._thread
        if thread is not None:
            thread.join(timeout)
        return self.status()

    def _run(self, target: Callable[[threading.Event, queue.Queue[str]], dict]) -> None:
        try:
            result = target(self._stop_event, self._command_queue)
            with self._lock:
                self._result = result
        except Exception as exc:  # pragma: no cover - defensive status path
            with self._lock:
                self._error = repr(exc)
        finally:
            with self._lock:
                self._finished_at = time.monotonic()
