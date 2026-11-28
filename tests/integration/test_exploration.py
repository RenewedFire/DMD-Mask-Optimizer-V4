from __future__ import annotations

from dataclasses import replace

import pytest

from dmd_optimizer.capture.text_dump import OccurrenceInput
from dmd_optimizer.corpus import Capture, append_capture
from dmd_optimizer.explore.coverage import CoverageError, summarize


def _source(**changes):
    value = Capture("a" * 64, "fixture.txt", "test", None, {}, True, 1, 1, 4, "native-u8", "identity-v1", None,
                    {"grammar": "fixture-v1"}, "b" * 64, "c" * 64)
    return replace(value, **changes)


def _frame(index: int, value: int) -> OccurrenceInput:
    return OccurrenceInput(0, index, index, None, "final-unknown", index, index + 1, index + 1, bytes([value]))


def test_resume_is_identical_and_revision_change_is_rejected(tmp_path):
    project = tmp_path / "corpus"
    first = append_capture(project, _source(), [_frame(0, 0), _frame(1, 1), _frame(2, 2)])
    checkpoint = tmp_path / "frontier.json"
    calls = iter((False, True))
    assert summarize(project, first.digest, checkpoint, lambda: next(calls, True)) is None
    assert summarize(project, first.digest, checkpoint, lambda: False) == summarize(project, first.digest, tmp_path / "fresh.json", lambda: False)

    second = append_capture(project, _source(source_sha256="d" * 64), [_frame(0, 3)])
    with pytest.raises(CoverageError, match="invalid checkpoint"):
        summarize(project, second.digest, checkpoint, lambda: False)
