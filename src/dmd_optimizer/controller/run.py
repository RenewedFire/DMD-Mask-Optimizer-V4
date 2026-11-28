"""Deadline-aware orchestration that retains only independently verified work."""

import hashlib
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Protocol

from .checkpoint import CheckpointError, load_checkpoint, save_checkpoint
from .model import InputIdentity, JobState, RunRequest, RunResult


class Clock(Protocol):
    def monotonic(self) -> float: ...


class StopToken(Protocol):
    def stopped(self) -> bool: ...


@dataclass(frozen=True)
class StageOutcome:
    verified_revision: str | None = None
    candidate_revision: str | None = None
    pending_frames: tuple[str, ...] = ()
    export_status: str | None = None


Stage = Callable[[float], StageOutcome | None]


@dataclass(frozen=True)
class JobStages:
    baseline: Stage | None = None
    analyze: Stage | None = None
    solve: Stage | None = None
    verify: Stage | None = None
    publish: Stage | None = None
    identity: InputIdentity | None = None
    finalization_reserve_seconds: float = 0.0


def _identity(request: RunRequest, stages: JobStages) -> InputIdentity:
    if stages.identity is not None:
        return stages.identity
    digest = hashlib.sha256(str(Path(request.rom_path)).encode("utf-8")).hexdigest()
    return InputIdentity(digest, "0" * 64, "0" * 64, (("controller", "v1"),))


def run_job(request: RunRequest, clock: Clock, stop: StopToken, *, stages: JobStages | None = None,
            progress: Callable[[str], None] | None = None) -> RunResult:
    """Run supplied stages within one monotonic budget and checkpoint the last verified scope."""
    stages = stages or JobStages()
    if request.budget_seconds < 0:
        raise ValueError("budget_seconds must be non-negative")
    start = clock.monotonic()
    deadline = start + request.budget_seconds
    run_id = f"run-{uuid.uuid4().hex[:12]}"
    run_dir = Path(request.output_dir) / run_id
    identity = _identity(request, stages)
    verified = export = None
    pending: list[str] = []
    export_status = "not-published"
    stop_reason = "completed"
    diagnostics: dict[str, str] = {}
    reserve = stages.finalization_reserve_seconds
    if reserve < 0:
        raise ValueError("finalization_reserve_seconds must be non-negative")
    if request.prior_run is not None:
        try:
            prior = load_checkpoint(request.prior_run, identity)
        except CheckpointError as error:
            diagnostics["resume"] = "identity-mismatch" if "identity" in str(error) else "unavailable"
            diagnostics["resume_error"] = str(error)
        else:
            verified, export = prior.last_verified_revision, prior.export_revision
            pending.extend(prior.pending_frames)
            export_status = str(prior.statuses.get("export_status", export_status))
            prior_reserve = prior.statuses.get("finalization_reserve_seconds", 0.0)
            if isinstance(prior_reserve, (int, float)):
                reserve = max(reserve, float(prior_reserve))
            diagnostics["resume"] = "compatible"
    for name in ("baseline", "analyze", "solve", "verify", "publish"):
        stage = getattr(stages, name)
        if stage is None:
            continue
        if stop.stopped():
            stop_reason = "cancelled"
            break
        if clock.monotonic() >= deadline:
            stop_reason = "deadline"
            break
        if name in {"analyze", "solve"} and deadline - clock.monotonic() <= reserve:
            stop_reason = "verification-reserve"
            break
        if progress:
            progress(name)
        stage_start = clock.monotonic()
        try:
            outcome = stage(deadline) or StageOutcome()
        except Exception as error:
            stop_reason = "worker-failed"
            diagnostics["error"] = str(error)
            break
        if outcome.verified_revision is not None:
            verified = outcome.verified_revision
            export = verified
        pending.extend(item for item in outcome.pending_frames if item not in pending)
        if outcome.export_status is not None:
            export_status = outcome.export_status
        if name in {"verify", "publish"}:
            reserve = max(reserve, clock.monotonic() - stage_start)
        state = JobState(identity, verified, export, tuple(pending),
                         {"export_status": export_status, "finalization_reserve_seconds": reserve})
        digest = save_checkpoint(run_dir, state)
        if stop.stopped():
            stop_reason = "cancelled"
            break
        if clock.monotonic() > deadline:
            stop_reason = "deadline"
            break
    else:
        digest = save_checkpoint(run_dir, JobState(identity, verified, export, tuple(pending),
                                                    {"export_status": export_status, "finalization_reserve_seconds": reserve}))
    if "digest" not in locals():
        digest = save_checkpoint(run_dir, JobState(identity, verified, export, tuple(pending),
                                                    {"export_status": export_status, "finalization_reserve_seconds": reserve}))
    end = clock.monotonic()
    return RunResult(run_id, stop_reason, "observed", "provisional", "unknown", export_status,
                     verified, export, len(pending), digest, max(0.0, min(end, deadline) - start),
                     max(0.0, end - deadline), diagnostics)
