"""Conservative recognition-family inference over immutable corpus revisions."""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, is_dataclass
from pathlib import Path
from typing import Sequence

from dmd_optimizer.corpus import CorpusError, Revision, iter_occurrences, read_capture_metadata, read_frames, read_revision
from dmd_optimizer.explore.coverage import CoverageReport

from .model import Family, FamilySet, FieldEvidence, OccurrenceKey
from .fields import FieldError, render_domain

_ALGORITHM = "finite-families-v1"


class FamilyError(ValueError):
    pass


def _canonical(value: object) -> bytes:
    def default(item: object):
        if is_dataclass(item):
            return asdict(item)
        if isinstance(item, bytes):
            return {"bytes": item.hex()}
        raise TypeError(f"not canonical JSON: {type(item).__name__}")
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=default).encode("utf-8")


def _digest(value: object) -> str:
    return hashlib.sha256(_canonical(value)).hexdigest()


def _scope(revision: Revision, project: Path, coverage: CoverageReport):
    if coverage.revision_digest != revision.digest:
        raise FamilyError("coverage revision does not match requested revision")
    try:
        stored = read_revision(project, revision.digest)
        metadata = read_capture_metadata(project, revision.digest)
    except CorpusError as error:
        raise FamilyError(str(error)) from error
    if stored != revision or coverage.capture_count != revision.capture_count or coverage.occurrence_count != revision.occurrence_count:
        raise FamilyError("coverage counts do not match revision")
    profiles = {item.source.profile_sha256 for item in metadata}
    if profiles != {coverage.profile_sha256}:
        raise FamilyError("coverage profile does not match revision")
    roms = {item.source.rom_sha256 for item in metadata}
    if roms != {coverage.rom_sha256}:
        raise FamilyError("coverage ROM does not match revision")
    training, validation = set(coverage.training_sessions), set(coverage.validation_sessions)
    if training & validation:
        raise FamilyError("coverage training and validation sessions overlap")
    rows = tuple(iter_occurrences(project, revision.digest))
    sessions = {(row.capture_id, row.session) for row in rows}
    if not training <= sessions or not validation <= sessions:
        raise FamilyError("coverage names an unknown session")
    return rows, training


def _family_id(frame_ids: tuple[str, ...], context: str, layout: str, animation: str) -> str:
    return _digest([_ALGORITHM, context, layout, animation, frame_ids])


def infer(revision: Revision, evidence: Sequence[FieldEvidence], *, project: Path, coverage: CoverageReport) -> FamilySet:
    """Return exact fallbacks, promoting only evidence whose domain reproduces input frames."""
    rows, training = _scope(revision, project, coverage)
    selected = [row for row in rows if (row.capture_id, row.session) in training]
    payloads = read_frames(project, (row.frame_id for row in selected))
    claimed: set[OccurrenceKey] = set()
    promoted: list[tuple[Family, tuple[OccurrenceKey, ...]]] = []
    families: list[Family] = []
    unresolved: list[tuple[str, str]] = []
    for item in sorted(evidence, key=lambda item: item.evidence_id):
        if item.revision_digest != revision.digest or item.source_kind not in {"synthetic-renderer", "rom-renderer"}:
            unresolved.append((item.evidence_id, "invalid-evidence-identity")); continue
        if any(key in claimed for key in item.occurrence_keys):
            unresolved.append((item.evidence_id, "conflicting-occurrence-expectation")); continue
        frame_ids = set(item.member_frame_ids)
        selected_by_key = {OccurrenceKey(row.capture_id, row.index): row for row in selected}
        if not item.occurrence_keys or not frame_ids or any(key not in selected_by_key for key in item.occurrence_keys):
            unresolved.append((item.evidence_id, "outside-training-scope")); continue
        if any(selected_by_key[key].frame_id not in frame_ids for key in item.occurrence_keys):
            unresolved.append((item.evidence_id, "occurrence-does-not-match-member")); continue
        if not frame_ids <= set(payloads):
            unresolved.append((item.evidence_id, "member-outside-training-scope")); continue
        if item.source_kind == "rom-renderer" and (len(item.source_digest) != 64 or any(char not in "0123456789abcdef" for char in item.source_digest) or not item.provenance.startswith("verified-rom-renderer:")):
            unresolved.append((item.evidence_id, "unverified-rom-renderer")); continue
        if item.template_frame_id not in payloads:
            unresolved.append((item.evidence_id, "unknown-template-frame")); continue
        source = next((meta.source for meta in read_capture_metadata(project, revision.digest)), None)
        try:
            domain = render_domain(payloads[item.template_frame_id], item.fields, item.joint_values,
                                   width=source.width, height=source.height, native_shades=source.native_shades)
        except FieldError:
            unresolved.append((item.evidence_id, "does-not-reproduce-observations")); continue
        observed = {payloads[frame_id] for frame_id in frame_ids if frame_id in payloads}
        if not observed or not observed <= set(domain):
            unresolved.append((item.evidence_id, "does-not-reproduce-observations")); continue
        required_ignore = tuple(index for index in range(len(domain[0])) if len({frame[index] for frame in domain}) > 1)
        family_id = _family_id(tuple(sorted(frame_ids)), item.context, item.layout_id, item.animation_state)
        must_compare = tuple(index for index in range(len(domain[0])) if index not in set(required_ignore))
        promoted.append((Family(family_id, "established-finite", item.context, item.layout_id, item.animation_state,
                                min(frame_ids), tuple(sorted(frame_ids)), tuple(dict.fromkeys(domain)), required_ignore,
                                must_compare, (item.evidence_id,), None), item.occurrence_keys))
        claimed.update(item.occurrence_keys)
    remaining = {}
    for row in selected:
        if OccurrenceKey(row.capture_id, row.index) in claimed:
            continue
        remaining.setdefault(row.frame_id, []).append(OccurrenceKey(row.capture_id, row.index))
    for frame_id in sorted(remaining):
        pixels = payloads[frame_id]
        family_id = _family_id((frame_id,), "exact", "exact", "exact")
        all_positions = tuple(range(len(pixels)))
        families.append(Family(family_id, "observed-only", "exact", "exact", "exact", frame_id, (frame_id,),
                               (pixels,), (), all_positions, (), None))
    assignments = [(key, family.family_id) for family, keys in promoted for key in keys]
    assignments.extend((key, _family_id((frame_id,), "exact", "exact", "exact"))
                       for frame_id, keys in remaining.items() for key in keys)
    assignments = tuple(sorted(assignments))
    families.extend(family for family, _ in promoted)
    frozen_families = tuple(sorted(families, key=lambda item: item.family_id))
    semantic = {"schema_version": 1, "algorithm_version": _ALGORITHM, "revision_digest": revision.digest,
                "profile_sha256": coverage.profile_sha256, "families": frozen_families, "assignments": assignments,
                "unresolved": sorted(unresolved)}
    return FamilySet(1, _ALGORITHM, revision.digest, coverage.profile_sha256, frozen_families,
                     assignments, tuple(sorted(unresolved)), _digest(semantic))
