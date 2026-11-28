from __future__ import annotations

import hashlib
import os
from pathlib import Path
from types import SimpleNamespace

import pytest

from dmd_optimizer.capture.text_dump import read_dump
from dmd_optimizer.corpus import Capture, append_capture
from dmd_optimizer.explore.coverage import summarize
from dmd_optimizer.families import infer
from scripts import lock_profile


def test_fixed_twister_dump_has_exact_observed_family_baseline(tmp_path):
    value = os.environ.get("DMD_TWISTER_DUMP")
    if value is None:
        pytest.skip("set DMD_TWISTER_DUMP to qualify fixed Twister families")
    path = Path(value)
    assert path.is_file(), f"DMD_TWISTER_DUMP does not name a file: {path}"
    before = hashlib.file_digest(path.open("rb"), "sha256").hexdigest()
    record, profile_sha256 = lock_profile._read_profile()
    assert before == record["dump_sha256"]
    profile = SimpleNamespace(width=record["width"], height=record["height"], native_shades=record["native_shades"])
    source = Capture(before, str(path), "VPinMAME", None, {"acquisition": "fixed-project-dump"}, True,
                     profile.width, profile.height, profile.native_shades, "native-u8", "identity-v1",
                     record["dump_format"]["tick_unit"], record["dump_format"], record["rom_sha256"], profile_sha256)
    project = tmp_path / "corpus"
    revision = append_capture(project, source, read_dump(path, profile))
    coverage = summarize(project, revision.digest, project / "coverage-frontier.json", lambda: False)
    result = infer(revision, (), project=project, coverage=coverage)

    assert (coverage.occurrence_count, coverage.unique_frame_count, coverage.repeat_count) == (14_443, 10_301, 4_142)
    assert len(result.assignments) == 14_443
    assert len(result.families) == 10_301
    assert {family.status for family in result.families} == {"observed-only"}
    assert result.unresolved == ()
    assert hashlib.file_digest(path.open("rb"), "sha256").hexdigest() == before
