from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest

from dmd_optimizer.capture.text_dump import OccurrenceInput


def source(**changes):
    from dmd_optimizer.corpus import Capture

    value = Capture(
        source_sha256="a" * 64, source_uri="capture.txt", producer="test", producer_version="1",
        configuration={"mode": "test"}, complete=True, width=2, height=2, native_shades=4,
        encoding="native-u8", normalization="identity-v1", tick_unit=None,
        timestamp_semantics={"grammar": "test-v1"}, rom_sha256="b" * 64, profile_sha256="c" * 64,
    )
    return replace(value, **changes)


def occurrence(index, pixels, *, tick=None, session=0):
    return OccurrenceInput(session, index, index if tick is None else tick, 1, "observed-delta",
                           index * 10, index * 10 + 9, index + 1, pixels)


def test_corpus_roundtrip_preserves_repeated_occurrences(tmp_path):
    from dmd_optimizer.corpus import append_capture, iter_occurrences, read_frame, read_frames, read_revision

    project = tmp_path / "corpus"
    revision = append_capture(project, source(), [occurrence(0, b"\x00\x01\x02\x03"), occurrence(1, b"\x00\x01\x02\x03"), occurrence(2, b"\x03\x02\x01\x00")])
    stored = list(iter_occurrences(project, revision.digest))

    assert (revision.capture_count, revision.occurrence_count, revision.unique_frame_count) == (1, 3, 2)
    assert [item.frame_id for item in stored[:2]] == [stored[0].frame_id, stored[0].frame_id]
    assert stored[2].frame_id != stored[0].frame_id
    assert [(item.session, item.original_tick, item.offset, item.end_offset, item.line) for item in stored] == [(0, 0, 0, 9, 1), (0, 1, 10, 19, 2), (0, 2, 20, 29, 3)]
    assert read_frame(project, stored[0].frame_id) == b"\x00\x01\x02\x03"
    assert read_frames(project, (stored[2].frame_id, stored[0].frame_id, stored[0].frame_id)) == {
        stored[0].frame_id: b"\x00\x01\x02\x03", stored[2].frame_id: b"\x03\x02\x01\x00",
    }
    assert read_revision(project).digest == revision.digest

    changed_geometry = append_capture(project, source(source_sha256="d" * 64, width=1, height=4), [occurrence(0, b"\x00\x01\x02\x03")])
    assert list(iter_occurrences(project, changed_geometry.digest))[-1].frame_id != stored[0].frame_id


def test_digest_collision_preserves_unequal_frames(tmp_path, monkeypatch):
    import dmd_optimizer.corpus.store as store
    from dmd_optimizer.corpus import append_capture, iter_occurrences, read_frame

    monkeypatch.setattr(store, "_lookup_digest", lambda _: "0" * 64)
    project = tmp_path / "corpus"
    revision = append_capture(project, source(), [occurrence(0, b"\x00\x00\x00\x00"), occurrence(1, b"\x03\x03\x03\x03")])
    rows = list(iter_occurrences(project, revision.digest))
    assert rows[0].frame_id != rows[1].frame_id
    assert [read_frame(project, row.frame_id) for row in rows] == [b"\x00" * 4, b"\x03" * 4]


def test_stable_digest_collision_and_invalid_first_session_reject(tmp_path, monkeypatch):
    import dmd_optimizer.corpus.store as store
    from dmd_optimizer.corpus import CorpusError, append_capture

    project = tmp_path / "corpus"
    monkeypatch.setattr(store, "_frame_id", lambda _: "f" * 128)
    with pytest.raises(CorpusError, match="collision"):
        append_capture(project, source(), [occurrence(0, b"\x00" * 4), occurrence(1, b"\x03" * 4)])
    with pytest.raises(CorpusError, match="sessions"):
        append_capture(tmp_path / "session", source(), [occurrence(0, b"\x00" * 4, session=1)])


def test_rejects_unrelated_database_and_non_string_json_keys(tmp_path):
    from dmd_optimizer.corpus import CorpusError, append_capture

    project = tmp_path / "unrelated"; project.mkdir()
    import sqlite3
    sqlite3.connect(project / "corpus.sqlite3").execute("CREATE TABLE unrelated (x INTEGER)").connection.close()
    with pytest.raises(CorpusError, match="unrelated"):
        append_capture(project, source(), [occurrence(0, b"\x00" * 4)])
    with pytest.raises(CorpusError, match="string keys"):
        append_capture(tmp_path / "keys", source(configuration={1: "bad"}), [occurrence(0, b"\x00" * 4)])


def test_new_capture_preserves_old_revision_and_identical_reimport_is_idempotent(tmp_path):
    from dmd_optimizer.corpus import append_capture, iter_occurrences

    project = tmp_path / "corpus"
    first = append_capture(project, source(), [occurrence(0, b"\x00" * 4)])
    assert append_capture(project, source(), [occurrence(0, b"\x00" * 4)]).digest == first.digest
    second = append_capture(project, source(source_sha256="d" * 64), [occurrence(0, b"\x01" * 4)])
    assert [row.original_tick for row in iter_occurrences(project, first.digest)] == [0]
    assert [row.original_tick for row in iter_occurrences(project, second.digest)] == [0, 0]


def test_iterator_failure_rolls_back_and_identity_mismatch_rejects(tmp_path):
    from dmd_optimizer.corpus import CorpusError, append_capture, read_revision

    project = tmp_path / "corpus"
    original = append_capture(project, source(), [occurrence(0, b"\x00" * 4)])

    def broken():
        yield occurrence(0, b"\x01" * 4)
        raise RuntimeError("source failed")

    with pytest.raises(RuntimeError, match="source failed"):
        append_capture(project, source(source_sha256="d" * 64), broken())
    assert read_revision(project).digest == original.digest
    with pytest.raises(CorpusError, match="ROM"):
        append_capture(project, source(rom_sha256="e" * 64), [occurrence(0, b"\x01" * 4)])


def test_recover_quarantines_orphan_and_corruption_fails(tmp_path):
    from dmd_optimizer.corpus import CorpusError, append_capture, iter_occurrences, read_frame, recover

    project = tmp_path / "corpus"
    revision = append_capture(project, source(), [occurrence(0, b"\x00" * 4)])
    orphan = project / "chunks" / "orphan.bin"
    orphan.write_bytes(b"unreferenced")
    recover(project)
    assert not orphan.exists()
    row = next(iter_occurrences(project, revision.digest))
    chunk = next((project / "chunks").glob("*.bin"))
    chunk.write_bytes(b"corrupt")
    with pytest.raises(CorpusError, match="chunk"):
        read_frame(project, row.frame_id)


def test_recover_rejects_missing_referenced_chunk_and_rename_failure_stays_unpublished(tmp_path, monkeypatch):
    import dmd_optimizer.corpus.store as store
    from dmd_optimizer.corpus import CorpusError, append_capture, read_revision, recover

    project = tmp_path / "corpus"
    first = append_capture(project, source(), [occurrence(0, b"\x00" * 4)])
    chunk = next((project / "chunks").glob("*.bin"))
    chunk.unlink()
    with pytest.raises(CorpusError, match="chunk"):
        recover(project)

    project = tmp_path / "rename"
    original = append_capture(project, source(), [occurrence(0, b"\x00" * 4)])
    real_replace = store.os.replace
    def renamed_then_failed(old, new):
        real_replace(old, new)
        raise OSError("simulated interruption after rename")
    monkeypatch.setattr(store.os, "replace", renamed_then_failed)
    with pytest.raises(OSError, match="simulated"):
        append_capture(project, source(source_sha256="d" * 64), [occurrence(0, b"\x01" * 4)])
    assert read_revision(project).digest == original.digest
