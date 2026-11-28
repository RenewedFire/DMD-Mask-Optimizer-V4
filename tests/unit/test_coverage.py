from __future__ import annotations

from dataclasses import replace

import pytest

from dmd_optimizer.capture.text_dump import OccurrenceInput


def _source(**changes):
    from dmd_optimizer.corpus import Capture

    value = Capture(
        source_sha256="a" * 64, source_uri="capture.txt", producer="test", producer_version="1",
        configuration={}, complete=True, width=2, height=2, native_shades=4,
        encoding="native-u8", normalization="identity-v1", tick_unit=None,
        timestamp_semantics={"grammar": "test-v1"}, rom_sha256="b" * 64, profile_sha256="c" * 64,
    )
    return replace(value, **changes)


def _occurrence(index: int, pixels: bytes, *, tick: int, session: int = 0) -> OccurrenceInput:
    return OccurrenceInput(session, index, tick, None, "final-unknown", index * 10, index * 10 + 9, index + 1, pixels)


def test_metadata_is_revision_scoped_and_missing_project_is_read_only(tmp_path):
    from dmd_optimizer.corpus import CorpusError, append_capture, iter_occurrences, read_capture_metadata, read_revision

    project = tmp_path / "corpus"
    first = append_capture(project, _source(), [_occurrence(0, b"\x00" * 4, tick=1)])
    append_capture(project, _source(source_sha256="d" * 64), [_occurrence(0, b"\x01" * 4, tick=2)])

    metadata = read_capture_metadata(project, first.digest)
    assert len(metadata) == 1
    assert metadata[0].ordinal == 0 and metadata[0].source.source_sha256 == "a" * 64
    missing = tmp_path / "missing-metadata"
    with pytest.raises(CorpusError, match="does not exist"):
        read_capture_metadata(missing, first.digest)
    assert not missing.exists()
    missing = tmp_path / "missing-revision"
    with pytest.raises(CorpusError, match="does not exist"):
        read_revision(missing, first.digest)
    assert not missing.exists()
    missing = tmp_path / "missing-occurrences"
    with pytest.raises(CorpusError, match="does not exist"):
        list(iter_occurrences(missing, first.digest))
    assert not missing.exists()


def test_summarize_counts_repeats_sessions_and_unknown_domains(tmp_path):
    from dmd_optimizer.corpus import append_capture
    from dmd_optimizer.explore.coverage import summarize

    project = tmp_path / "corpus"
    revision = append_capture(project, _source(), [
        _occurrence(0, b"\x00\x01\x02\x03", tick=10),
        _occurrence(1, b"\x00\x01\x02\x03", tick=10),
        _occurrence(2, b"\x03\x02\x01\x00", tick=3, session=1),
    ])
    report = summarize(project, revision.digest, tmp_path / "frontier.json", lambda: False)

    assert report is not None
    assert (report.occurrence_count, report.unique_frame_count, report.repeat_count) == (3, 2, 1)
    assert [(item.session, item.occurrence_count) for item in report.sessions] == [(0, 2), (1, 1)]
    assert report.total_reachable is None and report.coverage_status == "observed-only"
    assert report.validation_sessions == ()
    assert "reachable-output-domain-unproved" in report.obligations


def test_resume_matches_uninterrupted_and_rejects_tampered_checkpoint(tmp_path):
    import json
    from dmd_optimizer.corpus import append_capture
    from dmd_optimizer.explore.coverage import CoverageError, summarize

    project = tmp_path / "corpus"
    revision = append_capture(project, _source(), [
        _occurrence(0, b"\x00" * 4, tick=1), _occurrence(1, b"\x01" * 4, tick=2),
        _occurrence(2, b"\x01" * 4, tick=3),
    ])
    checkpoint = tmp_path / "resume.json"
    calls = iter((False, False, True))
    assert summarize(project, revision.digest, checkpoint, lambda: next(calls, True)) is None
    payload = json.loads(checkpoint.read_text(encoding="utf-8"))
    payload["frame_ids"] = ["forged", "forged"]
    first_session = next(iter(payload["sessions"].values()))
    first_session["frame_ids"] = ["forged", "forged"]
    from dmd_optimizer.explore.coverage import _checksum
    checksum_input = dict(payload); checksum_input.pop("checksum")
    payload["checksum"] = _checksum(checksum_input)
    checkpoint.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(CoverageError, match="checkpoint"):
        summarize(project, revision.digest, checkpoint, lambda: False)
    checkpoint.unlink()
    calls = iter((False, False, True))
    assert summarize(project, revision.digest, checkpoint, lambda: next(calls, True)) is None
    resumed = summarize(project, revision.digest, checkpoint, lambda: False)
    uninterrupted = summarize(project, revision.digest, tmp_path / "fresh.json", lambda: False)
    assert resumed == uninterrupted
    checkpoint.write_text('{"bad":true}', encoding="utf-8")
    with pytest.raises(CoverageError, match="checkpoint"):
        summarize(project, revision.digest, checkpoint, lambda: False)


def test_rejects_zero_cursor_checkpoint_with_forged_aggregates(tmp_path):
    import json
    from dmd_optimizer.corpus import append_capture
    from dmd_optimizer.explore.coverage import CoverageError, _checksum, summarize

    project = tmp_path / "corpus"
    revision = append_capture(project, _source(), [_occurrence(0, b"\x00" * 4, tick=1)])
    checkpoint = tmp_path / "resume.json"
    assert summarize(project, revision.digest, checkpoint, lambda: True) is None
    payload = json.loads(checkpoint.read_text(encoding="utf-8"))
    payload["frame_ids"] = ["forged"]
    unsigned = dict(payload)
    unsigned.pop("checksum")
    payload["checksum"] = _checksum(unsigned)
    checkpoint.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(CoverageError, match="checkpoint"):
        summarize(project, revision.digest, checkpoint, lambda: False)


def test_rejects_boolean_checkpoint_cursor(tmp_path):
    import json
    from dmd_optimizer.corpus import append_capture
    from dmd_optimizer.explore.coverage import CoverageError, _checksum, summarize

    project = tmp_path / "corpus"
    revision = append_capture(project, _source(), [_occurrence(0, b"\x00" * 4, tick=1)])
    checkpoint = tmp_path / "resume.json"
    assert summarize(project, revision.digest, checkpoint, lambda: True) is None
    payload = json.loads(checkpoint.read_text(encoding="utf-8"))
    payload["next_ordinal"] = True
    unsigned = dict(payload)
    unsigned.pop("checksum")
    payload["checksum"] = _checksum(unsigned)
    checkpoint.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(CoverageError, match="^invalid checkpoint"):
        summarize(project, revision.digest, checkpoint, lambda: False)


def test_resume_preserves_corpus_session_order_after_checkpoint_serialization(tmp_path):
    from dmd_optimizer.corpus import append_capture
    from dmd_optimizer.explore.coverage import summarize

    project = tmp_path / "corpus"
    occurrences = [
        _occurrence(index, bytes([index % 4]) * 4, tick=100 - index, session=index)
        for index in range(11)
    ]
    occurrences.append(_occurrence(11, b"\x00" * 4, tick=89, session=10))
    revision = append_capture(project, _source(), occurrences)
    checkpoint = tmp_path / "resume.json"
    calls = iter([False] * 11 + [True])
    assert summarize(project, revision.digest, checkpoint, lambda: next(calls, True)) is None

    resumed = summarize(project, revision.digest, checkpoint, lambda: False)
    uninterrupted = summarize(project, revision.digest, tmp_path / "fresh.json", lambda: False)

    assert resumed == uninterrupted
    assert [item.session for item in resumed.sessions] == list(range(11))
