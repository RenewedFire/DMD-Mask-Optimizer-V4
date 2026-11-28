import hashlib
import os
from pathlib import Path
from types import SimpleNamespace

import pytest

from dmd_optimizer.capture.text_dump import read_dump
from scripts import lock_profile


@pytest.fixture(scope="module")
def twister_dump():
    value = os.environ.get("DMD_TWISTER_DUMP")
    if value is None:
        pytest.skip("set DMD_TWISTER_DUMP to qualify the local Twister dump")
    path = Path(value)
    if not path.is_file():
        pytest.fail(f"DMD_TWISTER_DUMP does not name a file: {path}")
    record, _ = lock_profile._read_profile()
    return path, SimpleNamespace(
        width=record["width"], height=record["height"], native_shades=record["native_shades"],
        dump_format=record["dump_format"], dump_sha256=record["dump_sha256"],
    )


def test_twister_dump_is_complete_and_lossless(twister_dump):
    path, profile = twister_dump
    with path.open("rb") as source:
        assert hashlib.file_digest(source, "sha256").hexdigest() == profile.dump_sha256

    count = 0
    first = last = None
    previous_end = 0
    shades = set()
    payload_digests = set()
    repeated = 0
    sessions = set()
    duration_statuses = set()
    for occurrence in read_dump(path, profile):
        assert occurrence.index == count
        assert occurrence.offset == previous_end
        assert occurrence.offset < occurrence.end_offset <= path.stat().st_size
        assert len(occurrence.native_pixels) == 4096
        shades.update(occurrence.native_pixels)
        digest = hashlib.sha256(occurrence.native_pixels).digest()
        repeated += digest in payload_digests
        payload_digests.add(digest)
        sessions.add(occurrence.session)
        duration_statuses.add(occurrence.duration_status)
        first = occurrence if first is None else first
        last = occurrence
        previous_end = occurrence.end_offset
        count += 1

    assert count == 14_443
    assert shades == {0, 1, 2, 3}
    assert first is not None and first.original_tick == 0x00088B41
    assert last is not None and last.original_tick == 0x00227C3F
    assert previous_end == path.stat().st_size
    assert repeated == 4_142
    assert sessions == {0}
    assert duration_statuses == {"observed-delta", "final-unknown"}
    assert last.duration_ticks is None and last.duration_status == "final-unknown"
    assert profile.dump_format["tick_unit"] is None
