from pathlib import Path
from types import SimpleNamespace

import pytest


def profile(*, width=4, height=2):
    return SimpleNamespace(
        width=width,
        height=height,
        native_shades=4,
        dump_format={
            "grammar": "timestamped-text-v1",
            "tick_bits": 32,
            "tick_unit": None,
            "discontinuity_policy": "split-unknown",
            "timing_evidence": [],
        },
    )


def record(tick, rows, ending=b"\n"):
    return b"0x%08x" % tick + ending + ending.join(rows) + ending + ending


def write_dump(tmp_path, payload):
    path = tmp_path / "capture.txt"
    path.write_bytes(payload)
    return path


def test_reads_native_shades_and_repeats(tmp_path):
    from dmd_optimizer.capture.text_dump import read_dump

    payload = record(10, [b"0123", b"3210"]) + record(15, [b"0123", b"3210"])
    occurrences = list(read_dump(write_dump(tmp_path, payload), profile()))

    assert [(item.index, item.session, item.original_tick, item.native_pixels) for item in occurrences] == [
        (0, 0, 10, b"\x00\x01\x02\x03\x03\x02\x01\x00"),
        (1, 0, 15, b"\x00\x01\x02\x03\x03\x02\x01\x00"),
    ]
    assert [item.duration_ticks for item in occurrences] == [5, None]
    assert [item.duration_status for item in occurrences] == ["observed-delta", "final-unknown"]


@pytest.mark.parametrize("ending", [b"\n", b"\r\n"])
def test_preserves_byte_offsets_for_lf_and_crlf(tmp_path, ending):
    from dmd_optimizer.capture.text_dump import read_dump

    first = record(1, [b"0000", b"1111"], ending)
    second = record(2, [b"2222", b"3333"], ending)
    path = write_dump(tmp_path, first + second)
    occurrences = list(read_dump(path, profile()))

    assert [(item.offset, item.end_offset, item.line) for item in occurrences] == [
        (0, len(first), 1),
        (len(first), len(first) + len(second), 5),
    ]


@pytest.mark.parametrize(
    ("payload", "code"),
    [
        (record(1, [b"0000"]), "truncated-record"),
        (record(1, [b"0000", b"1111", b"2222"]), "missing-delimiter"),
        (record(1, [b"000", b"1111"]), "row-width"),
        (record(1, [b"00000", b"1111"]), "row-width"),
        (record(1, [b"0004", b"1111"]), "shade"),
        (record(1, [b"000g", b"1111"]), "shade"),
        (record(1, [b"000\xff", b"1111"]), "shade"),
        (b"0x100000000\n0000\n1111\n\n", "timestamp"),
        (b"0x00000001\n0000\n1111\n", "truncated-record"),
    ],
)
def test_rejects_invalid_record_at_source_position(tmp_path, payload, code):
    from dmd_optimizer.capture.text_dump import DumpParseError, read_dump

    path = write_dump(tmp_path, payload)
    with pytest.raises(DumpParseError) as raised:
        list(read_dump(path, profile()))

    error = raised.value
    assert error.code == code
    assert error.path == path
    assert error.offset >= 0
    assert error.line >= 1
    assert error.record_index == 0


def test_rejects_empty_file(tmp_path):
    from dmd_optimizer.capture.text_dump import DumpParseError, read_dump

    path = write_dump(tmp_path, b"")
    with pytest.raises(DumpParseError, match="empty-dump"):
        list(read_dump(path, profile()))


def test_rejects_paired_31_33_rows(tmp_path):
    from dmd_optimizer.capture.text_dump import DumpParseError, read_dump

    rows31 = [b"0" * 128] * 31
    rows33 = [b"0" * 128] * 33
    path = write_dump(tmp_path, record(1, rows31) + record(2, rows33))

    with pytest.raises(DumpParseError) as raised:
        list(read_dump(path, profile(width=128, height=32)))

    assert raised.value.code == "truncated-record"
    assert raised.value.record_index == 0


def test_decrease_starts_session_without_inventing_duration(tmp_path):
    from dmd_optimizer.capture.text_dump import read_dump

    payload = b"".join(record(tick, [b"0000", b"1111"]) for tick in [10, 15, 15, 3, 8])
    occurrences = list(read_dump(write_dump(tmp_path, payload), profile()))

    assert [item.session for item in occurrences] == [0, 0, 0, 1, 1]
    assert [item.duration_ticks for item in occurrences] == [5, 0, None, 5, None]
    assert [item.duration_status for item in occurrences] == [
        "observed-delta", "observed-delta", "discontinuity", "observed-delta", "final-unknown",
    ]


def test_wrap_is_not_guessed(tmp_path):
    from dmd_optimizer.capture.text_dump import read_dump

    payload = record(0xFFFFFFFE, [b"0000", b"1111"]) + record(1, [b"2222", b"3333"])
    occurrences = list(read_dump(write_dump(tmp_path, payload), profile()))

    assert [(item.session, item.duration_ticks, item.duration_status) for item in occurrences] == [
        (0, None, "discontinuity"), (1, None, "final-unknown"),
    ]
