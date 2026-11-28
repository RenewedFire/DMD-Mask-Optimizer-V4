"""Verification record for exportable and diagnostic Task 11 selections."""

from __future__ import annotations

from dataclasses import dataclass


class ExportVerificationError(ValueError):
    pass


@dataclass(frozen=True)
class VerificationRecord:
    input_occurrences: int
    mapped_occurrences: int
    omitted_occurrences: int
    wrong_family_matches: int
    unknown_matches: int
    native_verified: bool
    failure_witnesses: tuple[str, ...]


def verify_export(selection) -> VerificationRecord:
    """Validate complete diagnostic accounting before native publication exists."""
    mapped = sum(status == "mapped" for _, _, _, _, status in selection.occurrences)
    omitted = sum(status == "omitted" for _, _, _, _, status in selection.occurrences)
    unexplained = [frame for _, _, frame, _, status in selection.occurrences if status not in {"mapped", "omitted"}]
    if unexplained:
        raise ExportVerificationError(f"unexplained occurrence: {unexplained[0]}")
    omission_frames = {frame for frame, _ in selection.omissions}
    actual_omitted = {frame for _, _, frame, _, status in selection.occurrences if status == "omitted"}
    if actual_omitted != omission_frames:
        raise ExportVerificationError("omission evidence does not reconcile occurrence mapping")
    return VerificationRecord(len(selection.occurrences), mapped, omitted, 0, 0, False, tuple(reason for _, reason in selection.omissions))
