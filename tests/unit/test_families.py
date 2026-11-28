from __future__ import annotations

from dataclasses import replace

import pytest

from dmd_optimizer.capture.text_dump import OccurrenceInput
from dmd_optimizer.corpus import Capture, append_capture
from dmd_optimizer.explore.coverage import CoverageReport


def _source(**changes):
    value = Capture("a" * 64, "capture.txt", "test", "1", {}, True, 4, 2, 4,
                    "native-u8", "identity-v1", None, {"grammar": "test"}, "b" * 64, "c" * 64)
    return replace(value, **changes)


def _item(index, pixels, session=0):
    return OccurrenceInput(session, index, index, None, "final-unknown", index, index + 1, index + 1, pixels)


def _coverage(revision, training, validation=()):
    return CoverageReport(1, "dump-coverage-v1", revision.digest, "b" * 64, "c" * 64,
                          revision.capture_count, revision.occurrence_count, revision.unique_frame_count,
                          revision.occurrence_count - revision.unique_frame_count, (), tuple(training), tuple(validation),
                          None, "observed-only", (), "supplied-dumps")


def test_exact_baseline_preserves_training_occurrences_and_ignores_validation(tmp_path):
    from dmd_optimizer.families import infer

    project = tmp_path / "corpus"
    revision = append_capture(project, _source(), [_item(0, b"\x00" * 8), _item(1, b"\x00" * 8), _item(2, b"\x01" * 8, 1)])
    from dmd_optimizer.corpus import iter_occurrences
    rows = tuple(iter_occurrences(project, revision.digest))
    training = ((rows[0].capture_id, 0),)
    result = infer(revision, (), project=project, coverage=_coverage(revision, training, ((rows[0].capture_id, 1),)))

    assert len(result.families) == 1
    assert result.families[0].status == "observed-only"
    assert len(result.assignments) == 2
    assert {key.index for key, _ in result.assignments} == {0, 1}
    assert result.unresolved == ()


def test_scope_and_evidence_fail_closed(tmp_path):
    from dmd_optimizer.families import FamilyError, FieldEvidence, FieldSpec, OccurrenceKey, infer

    project = tmp_path / "corpus"
    revision = append_capture(project, _source(), [_item(0, b"\x00" * 8)])
    row = next(iter(__import__("dmd_optimizer.corpus", fromlist=["iter_occurrences"]).iter_occurrences(project, revision.digest)))
    coverage = _coverage(revision, ((row.capture_id, 0),))
    field = FieldSpec("score", (0, 0, 1, 1), ("1",), (("1", b"\x01"),), 1, 1, 1, "left", "reject")
    evidence = FieldEvidence("e", revision.digest, "synthetic-renderer", "d" * 64, "fixture", "score", "fixed", "still",
                             row.frame_id, (field,), (("1",),), (row.frame_id,), (OccurrenceKey(row.capture_id, 0),))
    result = infer(revision, (evidence,), project=project, coverage=coverage)
    assert result.unresolved == (("e", "does-not-reproduce-observations"),)
    with pytest.raises(FamilyError, match="coverage"):
        infer(revision, (), project=project, coverage=replace(coverage, revision_digest="d" * 64))
    with pytest.raises(FamilyError, match="ROM"):
        infer(revision, (), project=project, coverage=replace(coverage, rom_sha256="d" * 64))


def test_finite_field_family_uses_only_allowed_joint_values(tmp_path):
    from dmd_optimizer.families import FieldEvidence, FieldSpec, OccurrenceKey, infer

    project = tmp_path / "corpus"
    revision = append_capture(project, _source(), [_item(0, b"\x01\x00" + b"\x00" * 6), _item(1, b"\x02\x00" + b"\x00" * 6)])
    from dmd_optimizer.corpus import iter_occurrences
    rows = tuple(iter_occurrences(project, revision.digest))
    coverage = _coverage(revision, ((rows[0].capture_id, 0),))
    field = FieldSpec("score", (0, 0, 1, 1), ("1", "2"), (("1", b"\x01"), ("2", b"\x02")), 1, 1, 1, "left", "reject")
    evidence = FieldEvidence("score-fixture", revision.digest, "synthetic-renderer", "d" * 64, "independent fixture", "score", "fixed", "still",
                             rows[0].frame_id, (field,), (("1",), ("2",)), (rows[0].frame_id, rows[1].frame_id),
                             tuple(OccurrenceKey(row.capture_id, row.index) for row in rows))
    result = infer(revision, (evidence,), project=project, coverage=coverage)

    family = next(item for item in result.families if item.status == "established-finite")
    assert family.domain_pixels == (b"\x01\x00" + b"\x00" * 6, b"\x02\x00" + b"\x00" * 6)
    assert family.required_ignore == (0,)
    assert family.must_compare == tuple(range(1, 8))
    assert len(result.families) == 1 and result.unresolved == ()


def test_renderer_evidence_cannot_claim_validation_frames_or_unverified_rom_source(tmp_path):
    from dmd_optimizer.families import FieldEvidence, FieldSpec, OccurrenceKey, infer

    project = tmp_path / "corpus"
    revision = append_capture(project, _source(), [_item(0, b"\x00" * 8), _item(1, b"\x01" * 8, 1)])
    from dmd_optimizer.corpus import iter_occurrences
    training, validation = tuple(iter_occurrences(project, revision.digest))
    coverage = _coverage(revision, ((training.capture_id, 0),), ((validation.capture_id, 1),))
    field = FieldSpec("score", (0, 0, 1, 1), ("0",), (("0", b"\x00"),), 1, 1, 1, "left", "reject")
    evidence = FieldEvidence("scope", revision.digest, "synthetic-renderer", "d" * 64, "fixture", "score", "fixed", "still",
                             training.frame_id, (field,), (("0",),), (training.frame_id, validation.frame_id),
                             (OccurrenceKey(training.capture_id, training.index),))
    scoped = infer(revision, (evidence,), project=project, coverage=coverage)
    assert scoped.unresolved == (("scope", "member-outside-training-scope"),)
    rom = replace(evidence, evidence_id="rom", member_frame_ids=(training.frame_id,), source_kind="rom-renderer", source_digest="bad", provenance="fixture")
    unverified = infer(revision, (rom,), project=project, coverage=coverage)
    assert unverified.unresolved == (("rom", "unverified-rom-renderer"),)


def test_finite_domain_budget_is_not_sampled():
    from dmd_optimizer.families.fields import FieldError, render_domain
    from dmd_optimizer.families import FieldSpec

    field = FieldSpec("field", (0, 0, 1, 1), ("0",), (("0", b"\x00"),), 1, 1, 1, "left", "reject")
    with pytest.raises(FieldError, match="budget"):
        render_domain(b"\x00", (field,), tuple(("0",) for _ in range(4_097)), width=1, height=1, native_shades=4)
