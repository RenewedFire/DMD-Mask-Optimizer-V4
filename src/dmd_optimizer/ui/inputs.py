"""Validation for the bounded Twister desktop workflow."""

from __future__ import annotations

from pathlib import Path

from dmd_optimizer.controller.model import RunRequest


class InputValidationError(ValueError):
    """An actionable author-input problem."""


def validate_inputs(rom: Path, dumps: tuple[Path, ...], output: Path,
                    budget_seconds: float, prior_run: Path | None) -> RunRequest:
    """Build a request only for the pinned Twister profile and valid local paths."""
    rom = Path(rom)
    dumps = tuple(Path(dump) for dump in dumps)
    output = Path(output)
    if not rom.is_file():
        raise InputValidationError(f"ROM file is missing: {rom}")
    if rom.name.casefold() != "twst_405.zip":
        raise InputValidationError("unsupported ROM: this build supports twst_405.zip only")
    if any(not dump.is_file() for dump in dumps):
        missing = next(str(dump) for dump in dumps if not dump.is_file())
        raise InputValidationError(f"dump file is missing: {missing}")
    if any(dump.suffix.casefold() != ".txt" for dump in dumps):
        raise InputValidationError("optional dumps must be .txt files")
    if budget_seconds <= 0:
        raise InputValidationError("run limit must be greater than zero seconds")
    if prior_run is not None and not Path(prior_run).exists():
        raise InputValidationError(f"prior run is missing: {prior_run}")
    return RunRequest(rom, dumps, output, budget_seconds, prior_run)
