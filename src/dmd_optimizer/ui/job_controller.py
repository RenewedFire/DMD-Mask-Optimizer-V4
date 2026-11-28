"""Qt-safe adapter around the bounded optimizer controller."""

from __future__ import annotations

import threading
import time
import uuid
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Callable

from PySide6.QtCore import QObject, QThread, Signal, Slot

from dmd_optimizer.controller.model import RunRequest, RunResult
from dmd_optimizer.controller.run import run_job


@dataclass(frozen=True)
class ProgressView:
    """Display state derived from a real controller event."""

    stage: str
    elapsed_seconds: float
    remaining_seconds: float
    discovered_frames: int = 0
    tested_settings: int = 0
    verified_masks: int = 0
    pending_frames: int = 0
    status: str = "running"


class _StopToken:
    def __init__(self) -> None:
        self._event = threading.Event()

    def stop(self) -> None:
        self._event.set()

    def stopped(self) -> bool:
        return self._event.is_set()


class _Clock:
    def monotonic(self) -> float:
        return time.monotonic()


Runner = Callable[..., RunResult]


class _Worker(QObject):
    progress = Signal(str)
    result = Signal(object)
    failure = Signal(str)

    def __init__(self, runner: Runner, request: RunRequest, stop: _StopToken) -> None:
        super().__init__()
        self._runner = runner
        self._request = request
        self._stop = stop

    @Slot()
    def run(self) -> None:
        try:
            self.result.emit(self._runner(self._request, _Clock(), self._stop, progress=self.progress.emit))
        except Exception as error:  # surfaced to the window rather than killing a Qt thread
            self.failure.emit(str(error))


class JobController(QObject):
    """Run one bounded job on a worker thread and expose queued Qt signals."""

    progress = Signal(object)
    finished = Signal(object)
    failed = Signal(str)

    def __init__(self, *, runner: Runner = run_job) -> None:
        super().__init__()
        self._runner = runner
        self._thread: QThread | None = None
        self._worker: _Worker | None = None
        self._stop: _StopToken | None = None
        self._started_at: float | None = None
        self._request: RunRequest | None = None
        self._active_token: str | None = None
        self._pending_result: RunResult | None = None
        self._pending_failure: str | None = None

    @property
    def is_running(self) -> bool:
        return self._thread is not None

    def start(self, request: RunRequest) -> str:
        if self.is_running:
            raise RuntimeError("a job is already running")
        self._request = request
        self._started_at = time.monotonic()
        self._active_token = f"job-{uuid.uuid4().hex[:12]}"
        self._stop = _StopToken()
        self._thread = QThread(self)
        self._worker = _Worker(self._runner, request, self._stop)
        self._worker.moveToThread(self._thread)
        self._thread.started.connect(self._worker.run)
        self._worker.progress.connect(self._on_progress)
        self._worker.result.connect(self._capture_result)
        self._worker.failure.connect(self._capture_failure)
        self._worker.result.connect(self._thread.quit)
        self._worker.failure.connect(self._thread.quit)
        self._thread.finished.connect(self._worker.deleteLater)
        self._thread.finished.connect(self._thread.deleteLater)
        self._thread.finished.connect(self._finish_worker)
        self._thread.start()
        return self._active_token

    def cancel(self) -> None:
        if self._stop is not None:
            self._stop.stop()

    def resume(self, prior_run: Path, request: RunRequest) -> str:
        return self.start(replace(request, prior_run=prior_run))

    @Slot(str)
    def _on_progress(self, stage: str) -> None:
        request = self._request
        started = self._started_at
        if request is None or started is None:
            return
        elapsed = max(0.0, time.monotonic() - started)
        self.progress.emit(ProgressView(stage, elapsed, max(0.0, request.budget_seconds - elapsed)))

    @Slot(object)
    def _capture_result(self, result: RunResult) -> None:
        self._pending_result = result

    @Slot(str)
    def _capture_failure(self, message: str) -> None:
        self._pending_failure = message

    @Slot()
    def _finish_worker(self) -> None:
        result, failure = self._pending_result, self._pending_failure
        self._thread = None
        self._worker = None
        self._stop = None
        self._request = None
        self._started_at = None
        self._active_token = None
        self._pending_result = None
        self._pending_failure = None
        if result is not None:
            self.finished.emit(result)
        elif failure is not None:
            self.failed.emit(failure)
