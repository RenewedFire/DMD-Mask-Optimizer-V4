from __future__ import annotations

import hashlib
import os
from pathlib import Path
from types import SimpleNamespace

import pytest

from dmd_optimizer.capture.text_dump import read_dump
from dmd_optimizer.corpus import Capture, append_capture
from dmd_optimizer.explore.coverage import summarize
from scripts import lock_profile


@pytest.fixture(scope="module")
def qualified_twister(tmp_path_factory):
    value = os.environ.get("DMD_TWISTER_DUMP")
    if value is None:
        pytest.skip("set DMD_TWISTER_DUMP to qualify the fixed Twister dump")
    path = Path(value)
    if not path.is_file():
        pytest.fail(f"DMD_TWISTER_DUMP does not name a file: {path}")
    record, profile_sha256 = lock_profile._read_profile()
    digest = hashlib.file_digest(path.open("rb"), "sha256").hexdigest()
    assert digest == record["dump_sha256"]
    profile = SimpleNamespace(width=record["width"], height=record["height"], native_shades=record["native_shades"])
    source = Capture(digest, str(path), "VPinMAME", None, {"acquisition": "fixed-project-dump"}, True,
                     record["width"], record["height"], record["native_shades"], "native-u8", "identity-v1",
                     record["dump_format"]["tick_unit"], record["dump_format"], record["rom_sha256"], profile_sha256)
    project = tmp_path_factory.mktemp("twister-coverage")
    revision = append_capture(project, source, read_dump(path, profile))
    return path, project, revision


def test_fixed_twister_dump_has_observed_only_resumable_coverage(qualified_twister):
    path, project, revision = qualified_twister
    calls = iter([False] * 50 + [True])
    checkpoint = project / "frontier.json"
    assert summarize(project, revision.digest, checkpoint, lambda: next(calls, True)) is None
    resumed = summarize(project, revision.digest, checkpoint, lambda: False)
    uninterrupted = summarize(project, revision.digest, project / "fresh.json", lambda: False)

    assert resumed == uninterrupted
    assert (resumed.occurrence_count, resumed.unique_frame_count, resumed.repeat_count) == (14_443, 10_301, 4_142)
    assert len(resumed.sessions) == 1
    assert (resumed.sessions[0].first_tick, resumed.sessions[0].last_tick) == (0x00088B41, 0x00227C3F)
    assert resumed.total_reachable is None and resumed.coverage_status == "observed-only"
    assert resumed.validation_sessions == ()
    assert hashlib.file_digest(path.open("rb"), "sha256").hexdigest() == "f711aec5d42fdc423ca02bfd2c8f05c158afaee27a97acdbf59d532b81095b11"
