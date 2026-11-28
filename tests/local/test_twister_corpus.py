from __future__ import annotations

import hashlib
import os
from pathlib import Path
from types import SimpleNamespace

import pytest

from dmd_optimizer.capture.text_dump import read_dump
from dmd_optimizer.corpus import Capture, append_capture, iter_occurrences, read_frame
from scripts import lock_profile


@pytest.fixture(scope="module")
def twister_source():
    value = os.environ.get("DMD_TWISTER_DUMP")
    if value is None:
        pytest.skip("set DMD_TWISTER_DUMP to qualify the local Twister dump")
    path = Path(value)
    if not path.is_file():
        pytest.fail(f"DMD_TWISTER_DUMP does not name a file: {path}")
    record, profile_sha256 = lock_profile._read_profile()
    digest = hashlib.file_digest(path.open("rb"), "sha256").hexdigest()
    assert digest == record["dump_sha256"]
    profile = SimpleNamespace(width=record["width"], height=record["height"], native_shades=record["native_shades"], dump_format=record["dump_format"])
    capture = Capture(digest, path.name, "ColorizingDMD", None, {}, True, record["width"], record["height"], record["native_shades"], "native-u8", "identity-v1", record["dump_format"]["tick_unit"], record["dump_format"], record["rom_sha256"], profile_sha256)
    return path, profile, capture


def test_twister_dump_import_and_reimport(tmp_path, twister_source):
    path, profile, capture = twister_source
    project = tmp_path / "twister-corpus"
    revision = append_capture(project, capture, read_dump(path, profile))
    records = list(iter_occurrences(project, revision.digest))

    assert (revision.occurrence_count, revision.unique_frame_count, revision.capture_count, revision.complete) == (14_443, 10_301, 1, True)
    assert len(records) - len({row.frame_id for row in records}) == 4_142
    assert records[0].original_tick == 0x00088B41
    assert records[-1].original_tick == 0x00227C3F
    assert {row.session for row in records} == {0}
    assert records[-1].duration_ticks is None and records[-1].duration_status == "final-unknown"
    assert read_frame(project, records[0].frame_id) == next(read_dump(path, profile)).native_pixels
    assert append_capture(project, capture, read_dump(path, profile)).digest == revision.digest
