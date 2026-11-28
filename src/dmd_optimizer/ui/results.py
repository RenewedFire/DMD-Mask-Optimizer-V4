"""Pure result presentation state backed by verified paths."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Mapping

from dmd_optimizer.controller.model import RunResult


@dataclass(frozen=True)
class ResultView:
    stop_label: str
    recognition_label: str
    coverage_label: str
    optimality_label: str
    export_label: str
    pending_frames: int
    elapsed_seconds: float
    flush_seconds: float
    project_path: Path | None
    report_path: Path | None
    companion_folder: Path | None
    editable_project_enabled: bool
    report_enabled: bool
    folder_enabled: bool

    @classmethod
    def from_run(cls, result: RunResult, manifest: Mapping[str, object] | None) -> "ResultView":
        manifest = manifest or {}
        def existing(key: str) -> Path | None:
            value = manifest.get(key)
            path = Path(value) if isinstance(value, str) else None
            return path if path and path.exists() else None
        project, report, folder = existing("project_path"), existing("report_path"), existing("companion_folder")
        return cls(result.stop_reason, result.recognition_status, result.coverage_status,
                   result.optimality_status, result.export_status, result.pending_frames,
                   result.processing_seconds, result.flush_seconds, project, report, folder,
                   project is not None and result.export_status != "diagnostic-only",
                   report is not None, folder is not None and folder.is_dir())
