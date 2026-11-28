from __future__ import annotations

from pathlib import Path

import pytest


def _metadata(role: str) -> dict:
    return {
        "session_id": "run-1", "stream_role": role, "rom_sha256": "a" * 64,
        "profile_sha256": "b" * 64, "build_sha256": "c" * 64,
        "width": 2, "height": 2, "native_shades": 4, "encoding": "native-u8",
        "tick_unit": None, "hook_location": f"native::{role}",
    }


def _records():
    from dmd_optimizer.capture.live import TraceRecord
    return [TraceRecord(0, 10, b"\x00\x01\x02\x03"), TraceRecord(1, 10, b"\x00\x01\x02\x03"), TraceRecord(2, 3, b"\x03\x02\x01\x00")]


def test_compare_same_run_traces_and_preserve_repeats_and_reset(tmp_path):
    from dmd_optimizer.capture.live import compare_traces, read_trace, write_trace

    capture = tmp_path / "capture.bin"; consumer = tmp_path / "consumer.bin"
    write_trace(capture, _metadata("capture"), _records())
    write_trace(consumer, _metadata("consumer"), _records())

    parity = compare_traces(capture, consumer)
    assert parity.passed and parity.occurrence_count == 3 and parity.first_divergence is None
    occurrences = list(read_trace(capture))
    assert [item.session for item in occurrences] == [0, 0, 1]
    assert [item.duration_status for item in occurrences] == ["observed-delta", "discontinuity", "final-unknown"]
    assert occurrences[0].native_pixels == occurrences[1].native_pixels


@pytest.mark.parametrize("change", ["pixel", "extra", "clock", "encoding", "truncated"])
def test_compare_traces_rejects_differences_and_malformed_input(tmp_path, change):
    from dmd_optimizer.capture.live import CaptureError, compare_traces, write_trace

    capture = tmp_path / "capture.bin"; consumer = tmp_path / "consumer.bin"
    write_trace(capture, _metadata("capture"), _records())
    metadata = _metadata("consumer"); records = _records()
    if change == "pixel": records[1] = records[1].__class__(1, 10, b"\x03" * 4)
    if change == "extra": records.append(records[-1].__class__(3, 4, b"\x00" * 4))
    if change == "clock": records[1] = records[1].__class__(1, 11, records[1].pixels)
    if change == "encoding":
        metadata["encoding"] = "luminance-u8"
        with pytest.raises(CaptureError, match="luminance"):
            write_trace(consumer, metadata, records)
        return
    write_trace(consumer, metadata, records)
    if change == "truncated": consumer.write_bytes(consumer.read_bytes()[:-1])
    with pytest.raises(CaptureError):
        compare_traces(capture, consumer)


def test_capture_requires_completed_same_run_manifest(tmp_path):
    import hashlib
    import json
    from dmd_optimizer.capture.live import CaptureError, CaptureRequest, InputEvent, capture, write_trace
    from dmd_optimizer.rom.audit import AuditResult

    capture_path = tmp_path / "capture.bin"; consumer_path = tmp_path / "consumer.bin"
    write_trace(capture_path, _metadata("capture"), _records())
    write_trace(consumer_path, _metadata("consumer"), _records())
    audit = AuditResult(tmp_path / "rom.zip", "a" * 64, "d" * 64, "b" * 64, "fixture", "fixture_driver", ())
    request = CaptureRequest(audit, "b" * 64, tmp_path, tmp_path, {}, (InputEvent(0, 1, True),), 1000, 2000)
    with pytest.raises(CaptureError, match="completion"):
        list(capture(request))
    manifest = {"session_id": "run-1", "complete": True, "capture_trace": "capture.bin", "consumer_trace": "consumer.bin", "capture_sha256": hashlib.sha256(capture_path.read_bytes()).hexdigest(), "consumer_sha256": hashlib.sha256(consumer_path.read_bytes()).hexdigest(), "rom_content_sha256": "d" * 64, "profile_sha256": "b" * 64}
    (tmp_path / "completion.json").write_text(json.dumps(manifest), encoding="utf-8")
    assert [item.index for item in capture(request)] == [0, 1, 2]
    manifest["complete"] = False
    (tmp_path / "completion.json").write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(CaptureError, match="incomplete"):
        list(capture(request))
