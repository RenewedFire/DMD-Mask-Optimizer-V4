"""Write human-readable and raw Task 11 sidecar files."""

from __future__ import annotations

import csv
import hashlib
import html
import json
from dataclasses import dataclass
from pathlib import Path

from .compile import CompiledSelection


class ExportWriteError(ValueError):
    pass


@dataclass(frozen=True)
class ExportInventory:
    files: dict[str, str]

    @property
    def file_count(self) -> int:
        return len(self.files)


def _write(path: Path, data: bytes) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return hashlib.sha256(data).hexdigest()


def write_separate_exports(selection: CompiledSelection, folder: Path) -> ExportInventory:
    folder = Path(folder)
    if folder.exists():
        raise ExportWriteError(f"output already exists: {folder}")
    ids = [reference.frame_id for reference in selection.references]
    if len(ids) != len(set(ids)):
        raise ExportWriteError("duplicate reference frame ID")
    files: dict[str, str] = {}
    for reference in selection.references:
        if not reference.native_pixels or max(reference.native_pixels) > 3:
            raise ExportWriteError(f"invalid native pixels for {reference.frame_id}")
        relative = f"reference_frames/{reference.frame_id}.bin"
        files[relative] = _write(folder / relative, reference.native_pixels)
    masks = {"schema_version": 1, "masks": []}
    files["masks.json"] = _write(folder / "masks.json", json.dumps(masks, sort_keys=True, separators=(",", ":")).encode())
    optimization = {"pool_digest": selection.pool_digest, "solution_digest": selection.solution_digest, "reference_count": len(selection.references)}
    files["optimization.json"] = _write(folder / "optimization.json", json.dumps(optimization, sort_keys=True, separators=(",", ":")).encode())
    coverage = {"revision_digest": selection.revision_digest, "family_digest": selection.family_digest, "mapped_occurrences": len(selection.occurrences), "omissions": list(selection.omissions)}
    files["coverage.json"] = _write(folder / "coverage.json", json.dumps(coverage, sort_keys=True, separators=(",", ":")).encode())
    mapping = folder / "frame_mapping.csv"
    mapping.parent.mkdir(parents=True, exist_ok=True)
    with mapping.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=("capture_id", "index", "frame_id", "family_id", "status"))
        writer.writeheader()
        for capture, index, frame, family, status in selection.occurrences:
            writer.writerow({"capture_id": capture, "index": index, "frame_id": frame, "family_id": family or "", "status": status})
    files["frame_mapping.csv"] = hashlib.sha256(mapping.read_bytes()).hexdigest()
    report = f"<html><body><h1>Task 11 export</h1><p>References: {len(selection.references)}</p><p>Omissions: {html.escape(str(len(selection.omissions)))}</p></body></html>"
    files["report.html"] = _write(folder / "report.html", report.encode("utf-8"))
    return ExportInventory(dict(sorted(files.items())))
