"""Behavior tests for the desktop background job adapter."""

from pathlib import Path
import time

import pytest
from PySide6.QtCore import QTimer

from dmd_optimizer.controller.model import RunRequest, RunResult
from dmd_optimizer.ui.job_controller import JobController


def request(tmp_path: Path) -> RunRequest:
    return RunRequest(tmp_path / "twst_405.zip", (), tmp_path / "runs", budget_seconds=10)


def completed_result() -> RunResult:
    return RunResult("run-finished", "completed", "observed", "covered", "optimal",
                     "diagnostic-only", "verified-1", None, 3, "digest", 0.1, 0.0, {})


def test_start_emits_progress_then_result_without_blocking_qt_loop(qtbot, tmp_path):
    """Replacing the worker thread with a direct call would freeze the desktop."""
    timer_ticks: list[str] = []

    def runner(request, clock, stop, *, progress):
        progress("analyze")
        time.sleep(0.04)
        progress("verify")
        return completed_result()

    controller = JobController(runner=runner)
    with qtbot.waitSignal(controller.progress, timeout=1_000) as progress, \
            qtbot.waitSignal(controller.finished, timeout=1_000) as finished:
        QTimer.singleShot(5, lambda: timer_ticks.append("tick"))
        token = controller.start(request(tmp_path))

    assert token.startswith("job-")
    assert progress.args[0].stage == "analyze"
    assert finished.args[0].run_id == "run-finished"
    assert timer_ticks == ["tick"]
    assert controller.is_running is False


def test_cancel_signals_active_job_and_rejects_second_run(qtbot, tmp_path):
    """Removing the stop token or run guard would lose a cancel or run jobs concurrently."""
    entered = []

    def runner(request, clock, stop, *, progress):
        entered.append(True)
        while not stop.stopped():
            time.sleep(0.005)
        return RunResult("run-cancelled", "cancelled", "observed", "provisional", "unknown",
                         "not-published", None, None, 0, "digest", 0.1, 0.0, {})

    controller = JobController(runner=runner)
    controller.start(request(tmp_path))
    qtbot.waitUntil(lambda: bool(entered), timeout=1_000)
    with pytest.raises(RuntimeError, match="already running"):
        controller.start(request(tmp_path))
    with qtbot.waitSignal(controller.finished, timeout=1_000) as finished:
        controller.cancel()

    assert finished.args[0].stop_reason == "cancelled"
    assert controller.is_running is False


def test_worker_exception_becomes_visible_failure(qtbot, tmp_path):
    """Removing worker exception handling would leave the UI with a stuck run."""
    def runner(request, clock, stop, *, progress):
        raise RuntimeError("simulated stage failure")

    controller = JobController(runner=runner)
    with qtbot.waitSignal(controller.failed, timeout=1_000) as failure:
        controller.start(request(tmp_path))

    assert "simulated stage failure" in failure.args[0]
    qtbot.waitUntil(lambda: not controller.is_running, timeout=1_000)
