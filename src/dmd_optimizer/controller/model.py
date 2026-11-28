"""Value objects shared by the bounded job controller."""

from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class InputIdentity:
    rom_sha256: str
    profile_sha256: str
    corpus_revision: str
    algorithms: tuple[tuple[str, str], ...]
    native_export_sha256: str | None = None


@dataclass(frozen=True)
class JobState:
    identity: InputIdentity
    last_verified_revision: str | None
    export_revision: str | None
    pending_frames: tuple[str, ...]
    statuses: dict[str, Any]


@dataclass(frozen=True)
class RunRequest:
    rom_path: Path
    dump_paths: tuple[Path, ...]
    output_dir: Path
    budget_seconds: float = 1800
    prior_run: Path | None = None

    def __post_init__(self) -> None:
        if self.budget_seconds < 0:
            raise ValueError("budget_seconds must be non-negative")


@dataclass(frozen=True)
class RunResult:
    run_id: str
    stop_reason: str
    recognition_status: str
    coverage_status: str
    optimality_status: str
    export_status: str
    last_verified_revision: str | None
    export_revision: str | None
    pending_frames: int
    checkpoint_digest: str | None
    processing_seconds: float
    flush_seconds: float
    diagnostics: dict[str, Any]
