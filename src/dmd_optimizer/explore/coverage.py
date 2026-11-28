"""Deterministic, observed-only coverage reports for immutable corpus revisions."""

from __future__ import annotations

import hashlib
import json
import os
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Callable

from dmd_optimizer.corpus import CorpusError, iter_occurrences, read_capture_metadata, read_revision

_ALGORITHM = "dump-coverage-v1"
_OBLIGATIONS = (
    "reachable-output-domain-unproved", "language-settings-domain-unknown",
    "initial-state-domain-unknown", "gameplay-mode-coverage-unproved",
    "independent-validation-capture-missing", "timestamp-unit-unknown",
)


class CoverageError(ValueError):
    pass


@dataclass(frozen=True)
class SessionSummary:
    capture_id: str
    session: int
    occurrence_count: int
    unique_frame_count: int
    first_index: int
    last_index: int
    first_tick: int
    last_tick: int


@dataclass(frozen=True)
class CoverageReport:
    schema_version: int
    algorithm_version: str
    revision_digest: str
    rom_sha256: str
    profile_sha256: str
    capture_count: int
    occurrence_count: int
    unique_frame_count: int
    repeat_count: int
    sessions: tuple[SessionSummary, ...]
    training_sessions: tuple[tuple[str, int], ...]
    validation_sessions: tuple[tuple[str, int], ...]
    total_reachable: int | None
    coverage_status: str
    obligations: tuple[str, ...]
    source_scope: str


def _canonical(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def _checksum(value: dict) -> str:
    return hashlib.sha256(_canonical(value)).hexdigest()


def _write(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_bytes(_canonical(value))
    os.replace(temporary, path)


def _identity(revision_digest: str, metadata) -> dict:
    if not metadata:
        raise CoverageError("revision has no captures")
    roms = {item.source.rom_sha256 for item in metadata}
    profiles = {item.source.profile_sha256 for item in metadata}
    if len(roms) != 1 or len(profiles) != 1:
        raise CoverageError("revision capture identities disagree")
    return {"schema_version": 1, "algorithm_version": _ALGORITHM, "revision_digest": revision_digest,
            "rom_sha256": roms.pop(), "profile_sha256": profiles.pop()}


def _empty(identity: dict) -> dict:
    return {**identity, "next_ordinal": 0, "occurrence_count": 0, "frame_ids": [], "sessions": {}}


def _load_checkpoint(path: Path, identity: dict) -> dict:
    if not path.exists():
        return _empty(identity)
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        checksum = value.pop("checksum")
        if checksum != _checksum(value) or any(value.get(key) != expected for key, expected in identity.items()):
            raise ValueError
        if type(value["next_ordinal"]) is not int or value["next_ordinal"] < 0:
            raise ValueError
        if not isinstance(value["frame_ids"], list) or not isinstance(value["sessions"], dict):
            raise ValueError
        return value
    except (OSError, KeyError, TypeError, ValueError, json.JSONDecodeError) as error:
        raise CoverageError(f"invalid checkpoint: {path}") from error


def _save_checkpoint(path: Path, state: dict) -> None:
    value = dict(state)
    value["checksum"] = _checksum(value)
    _write(path, value)


def _apply(state: dict, occurrence) -> None:
    key = f"{occurrence.capture_id}:{occurrence.session}"
    session = state["sessions"].get(key)
    if session is None:
        session = {"capture_id": occurrence.capture_id, "session": occurrence.session,
                   "occurrence_count": 0, "frame_ids": [], "first_index": occurrence.index,
                   "last_index": occurrence.index, "first_tick": occurrence.original_tick,
                   "last_tick": occurrence.original_tick}
        state["sessions"][key] = session
    session["occurrence_count"] += 1
    session["frame_ids"].append(occurrence.frame_id)
    session["last_index"] = occurrence.index
    session["last_tick"] = occurrence.original_tick
    state["frame_ids"].append(occurrence.frame_id)
    state["occurrence_count"] += 1
    state["next_ordinal"] += 1


def _report(state: dict, revision, identity: dict) -> CoverageReport:
    if state["occurrence_count"] != revision.occurrence_count:
        raise CoverageError("checkpoint occurrence count does not match revision")
    sessions = tuple(SessionSummary(
        value["capture_id"], value["session"], value["occurrence_count"], len(set(value["frame_ids"])),
        value["first_index"], value["last_index"], value["first_tick"], value["last_tick"],
    ) for value in state["sessions"].values())
    training = tuple((value.capture_id, value.session) for value in sessions)
    return CoverageReport(1, _ALGORITHM, identity["revision_digest"], identity["rom_sha256"], identity["profile_sha256"],
                          revision.capture_count, state["occurrence_count"], len(set(state["frame_ids"])),
                          state["occurrence_count"] - len(set(state["frame_ids"])), sessions, training, (), None,
                          "observed-only", _OBLIGATIONS, "supplied-dumps")


def _report_json(report: CoverageReport) -> dict:
    value = asdict(report)
    value["sessions"] = [asdict(item) for item in report.sessions]
    value["training_sessions"] = [list(item) for item in report.training_sessions]
    value["validation_sessions"] = []
    value["obligations"] = list(report.obligations)
    return value


def summarize(project: Path, revision_digest: str, checkpoint_path: Path, stop: Callable[[], bool]) -> CoverageReport | None:
    """Summarize a revision and save an atomic checkpoint on cancellation."""
    try:
        metadata = read_capture_metadata(project, revision_digest)
        revision = read_revision(project, revision_digest)
    except CorpusError as error:
        raise CoverageError(str(error)) from error
    identity = _identity(revision_digest, metadata)
    checkpoint_path = Path(checkpoint_path)
    state = _load_checkpoint(checkpoint_path, identity)
    cursor = state["next_ordinal"]
    expected = _empty(identity)
    for ordinal, occurrence in enumerate(iter_occurrences(project, revision_digest)):
        if ordinal == cursor:
            break
        if stop():
            return None
        _apply(expected, occurrence)
    if expected["next_ordinal"] != cursor:
        raise CoverageError("invalid checkpoint cursor")
    if expected != state:
        raise CoverageError("checkpoint does not match processed revision prefix")
    state = expected
    for ordinal, occurrence in enumerate(iter_occurrences(project, revision_digest)):
        if ordinal < cursor:
            continue
        if stop():
            _save_checkpoint(checkpoint_path, state)
            return None
        _apply(state, occurrence)
    report = _report(state, revision, identity)
    _write(checkpoint_path.with_name("coverage.json"), _report_json(report))
    return report
