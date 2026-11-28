"""Stable intermediate representation for Task 11 outputs."""

from __future__ import annotations

from dataclasses import dataclass

from dmd_optimizer.corpus.store import iter_occurrences


@dataclass(frozen=True)
class CompiledReference:
    family_id: str
    option_id: str
    frame_id: str
    native_pixels: bytes
    ignore_bitmap: bytes | None
    ordinal: int


@dataclass(frozen=True)
class CompiledSelection:
    revision_digest: str
    pool_digest: str
    family_digest: str
    solution_digest: str
    references: tuple[CompiledReference, ...]
    occurrences: tuple[tuple[str, int, str, str | None, str], ...]
    omissions: tuple[tuple[str, str], ...]


def compile_records(frame_families, selected_family_ids, occurrences):
    """Create complete occurrence accounting for a selected family scope."""
    records = []
    for capture_id, index, frame_id in occurrences:
        family_id = frame_families.get(frame_id)
        if family_id is None:
            raise ValueError(f"corpus frame has no family: {frame_id}")
        records.append((capture_id, index, frame_id, family_id, "mapped" if family_id in selected_family_ids else "omitted"))
    return tuple(records)


def compile_selection(result, pool, families, decision, corpus_path, selected_family_ids=None) -> CompiledSelection:
    """Compile the exact Task 10 choice into stable references and accounting."""
    if (decision.revision_digest, decision.pool_digest, decision.family_digest, decision.solution_digest) != (result.revision_digest, pool.digest, families.digest, result.digest):
        raise ValueError("export decision identity mismatch")
    selected = frozenset(selected_family_ids or (family.family_id for family in families.families))
    options = {option.option_id: option for option in pool.options}
    by_family = {family.family_id: family for family in families.families}
    if not selected <= by_family.keys():
        raise ValueError("selected unknown family")
    references = []
    for ordinal, (family_id, option_id) in enumerate(sorted(result.assignment)):
        if family_id not in selected:
            continue
        option, family = options[option_id], by_family[family_id]
        references.append(CompiledReference(family_id, option_id, option.reference_frame_id, family.domain_pixels[0], option.ignore, ordinal))
    frame_families = {frame_id: family.family_id for family in families.families for frame_id in family.observed_frame_ids}
    corpus_occurrences = tuple((item.capture_id, item.index, item.frame_id) for item in iter_occurrences(corpus_path, decision.revision_digest))
    records = compile_records(frame_families, selected, corpus_occurrences)
    omissions = tuple(sorted({(frame, "family omitted from selected scope") for _, _, frame, _, status in records if status == "omitted"}))
    return CompiledSelection(decision.revision_digest, decision.pool_digest, decision.family_digest, decision.solution_digest, tuple(references), records, omissions)
