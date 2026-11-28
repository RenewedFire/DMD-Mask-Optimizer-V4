"""Immutable contracts for evidence-backed DMD recognition families."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, order=True)
class OccurrenceKey:
    capture_id: str
    index: int


@dataclass(frozen=True)
class FrameSample:
    frame_id: str
    pixels: bytes
    occurrences: tuple[OccurrenceKey, ...]


@dataclass(frozen=True)
class FieldSpec:
    name: str
    bounds: tuple[int, int, int, int]
    values: tuple[str, ...]
    glyphs: tuple[tuple[str, bytes], ...]
    glyph_width: int
    glyph_height: int
    advance: int
    alignment: str
    overflow: str


@dataclass(frozen=True)
class FieldEvidence:
    evidence_id: str
    revision_digest: str
    source_kind: str
    source_digest: str
    provenance: str
    context: str
    layout_id: str
    animation_state: str
    template_frame_id: str
    fields: tuple[FieldSpec, ...]
    joint_values: tuple[tuple[str, ...], ...]
    member_frame_ids: tuple[str, ...]
    occurrence_keys: tuple[OccurrenceKey, ...]


@dataclass(frozen=True)
class Family:
    family_id: str
    status: str
    context: str
    layout_id: str
    animation_state: str
    reference_frame_id: str
    observed_frame_ids: tuple[str, ...]
    domain_pixels: tuple[bytes, ...]
    required_ignore: tuple[int, ...]
    must_compare: tuple[int, ...]
    evidence_ids: tuple[str, ...]
    reason: str | None


@dataclass(frozen=True)
class FamilySet:
    schema_version: int
    algorithm_version: str
    revision_digest: str
    profile_sha256: str
    families: tuple[Family, ...]
    assignments: tuple[tuple[OccurrenceKey, str], ...]
    unresolved: tuple[tuple[str, str], ...]
    digest: str
