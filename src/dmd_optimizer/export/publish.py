"""Atomic publication for verified or diagnostic Task 11 bundles."""

from __future__ import annotations

import json
import os
import uuid
from dataclasses import dataclass
from pathlib import Path

from .files import ExportInventory, write_separate_exports
from dmd_optimizer.verify.exported import verify_export


class ExportPublishError(ValueError):
    pass


@dataclass(frozen=True)
class ExportRecord:
    status: str
    folder: Path
    inventory: ExportInventory
    reasons: tuple[str, ...]


def publish_diagnostic(selection, root: Path, *, reasons: tuple[str, ...], run_id: str | None = None) -> ExportRecord:
    """Publish a fully accounted diagnostic bundle without an editor project."""
    verification = verify_export(selection)
    if verification.input_occurrences != verification.mapped_occurrences + verification.omitted_occurrences:
        raise ExportPublishError("occurrence accounting is incomplete")
    root = Path(root)
    root.mkdir(parents=True, exist_ok=True)
    name = run_id or f"task11-{uuid.uuid4().hex[:12]}"
    target = root / name
    staging = root / f".{name}.{uuid.uuid4().hex}.staging"
    if target.exists():
        raise ExportPublishError(f"output already exists: {target}")
    try:
        inventory = write_separate_exports(selection, staging)
        diagnostic = {
            "status": "diagnostic-only", "reasons": list(reasons),
            "input_occurrences": verification.input_occurrences,
            "mapped_occurrences": verification.mapped_occurrences,
            "omitted_occurrences": verification.omitted_occurrences,
            "native_verified": verification.native_verified,
        }
        (staging / "diagnostic.json").write_text(json.dumps(diagnostic, sort_keys=True, separators=(",", ":")), encoding="utf-8")
        inventory_payload = dict(inventory.files)
        inventory_payload["diagnostic.json"] = __import__("hashlib").sha256((staging / "diagnostic.json").read_bytes()).hexdigest()
        (staging / "inventory.json").write_text(json.dumps(inventory_payload, sort_keys=True, separators=(",", ":")), encoding="utf-8")
        for relative, digest in inventory_payload.items():
            if __import__("hashlib").sha256((staging / relative).read_bytes()).hexdigest() != digest:
                raise ExportPublishError(f"inventory read-back mismatch: {relative}")
        os.replace(staging, target)
    except OSError as error:
        raise ExportPublishError(f"could not publish diagnostic bundle: {error}") from error
    return ExportRecord("diagnostic-only", target, inventory, reasons)
