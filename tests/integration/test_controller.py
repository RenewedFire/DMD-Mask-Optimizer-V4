from dataclasses import dataclass

import pytest


@dataclass
class Clock:
    now: float = 0.0

    def monotonic(self):
        return self.now


@dataclass
class Stop:
    value: bool = False

    def stopped(self):
        return self.value


def request(tmp_path, budget=1800):
    from dmd_optimizer.controller.model import RunRequest
    return RunRequest(tmp_path / "twst_405.zip", (), tmp_path / "runs", budget)


def test_controller_preserves_last_verified_export_when_late_frame_arrives(tmp_path):
    from dmd_optimizer.controller.run import JobStages, StageOutcome, run_job

    stages = JobStages(
        baseline=lambda deadline: StageOutcome(verified_revision="baseline"),
        analyze=lambda deadline: StageOutcome(pending_frames=("late-frame",)),
        solve=lambda deadline: StageOutcome(candidate_revision="candidate"),
        verify=lambda deadline: StageOutcome(verified_revision="verified"),
        publish=lambda deadline: StageOutcome(export_status="diagnostic-only"),
    )
    result = run_job(request(tmp_path), Clock(), Stop(), stages=stages)
    assert result.export_revision == result.last_verified_revision == "verified"
    assert result.pending_frames == 1
    assert result.export_status == "diagnostic-only"


def test_controller_stops_scheduling_at_deadline_and_reports_flush_time(tmp_path):
    from dmd_optimizer.controller.run import JobStages, StageOutcome, run_job

    clock, calls = Clock(), []
    def baseline(deadline):
        calls.append("baseline")
        clock.now = deadline + 0.1
        return StageOutcome(verified_revision="baseline")
    stages = JobStages(baseline=baseline, analyze=lambda deadline: calls.append("analyze"))
    result = run_job(request(tmp_path, budget=1), clock, Stop(), stages=stages)
    assert calls == ["baseline"]
    assert result.stop_reason == "deadline"
    assert result.export_revision == "baseline"
    assert result.flush_seconds == pytest.approx(0.1)


def test_controller_reports_cancellation_and_worker_failure_without_losing_baseline(tmp_path):
    from dmd_optimizer.controller.run import JobStages, StageOutcome, run_job

    stop = Stop()
    def baseline(deadline):
        stop.value = True
        return StageOutcome(verified_revision="baseline")
    cancelled = run_job(request(tmp_path), Clock(), stop, stages=JobStages(baseline=baseline))
    assert cancelled.stop_reason == "cancelled"
    assert cancelled.export_revision == "baseline"

    def failed(deadline):
        raise RuntimeError("worker exited")
    crashed = run_job(request(tmp_path), Clock(), Stop(), stages=JobStages(baseline=lambda deadline: StageOutcome(verified_revision="baseline"), analyze=failed))
    assert crashed.stop_reason == "worker-failed"
    assert crashed.export_revision == "baseline"
    assert "worker exited" in crashed.diagnostics["error"]


def test_controller_reserves_measured_finalization_time_before_more_analysis(tmp_path):
    from dmd_optimizer.controller.run import JobStages, StageOutcome, run_job

    clock, calls = Clock(), []
    def baseline(deadline):
        calls.append("baseline")
        clock.now = 0.3
        return StageOutcome(verified_revision="baseline")
    stages = JobStages(
        baseline=baseline,
        analyze=lambda deadline: calls.append("analyze"),
        finalization_reserve_seconds=0.8,
    )
    result = run_job(request(tmp_path, budget=1), clock, Stop(), stages=stages)
    assert calls == ["baseline"]
    assert result.stop_reason == "verification-reserve"
    assert result.export_revision == "baseline"
