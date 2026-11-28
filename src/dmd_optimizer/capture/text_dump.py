"""Strict streaming reader for the timestamped ColorizingDMD text dump."""

from __future__ import annotations

import re
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Iterator


_HEADER = re.compile(rb"0x[0-9a-fA-F]{8}\Z")


class DumpParseError(ValueError):
    """A dump violates the selected grammar at a precise source position."""

    def __init__(self, path: Path, offset: int, line: int, record_index: int, code: str):
        self.path = path
        self.offset = offset
        self.line = line
        self.record_index = record_index
        self.code = code
        super().__init__(f"{path}:{line}:{offset}: record {record_index}: {code}")


@dataclass(frozen=True)
class OccurrenceInput:
    session: int
    index: int
    original_tick: int
    duration_ticks: int | None
    duration_status: str
    offset: int
    end_offset: int
    line: int
    native_pixels: bytes


def _line(handle, *, maximum: int, path: Path, offset: int, line: int, record_index: int) -> bytes:
    value = handle.readline(maximum + 2)
    if len(value) > maximum + 1 and not value.endswith(b"\n"):
        raise DumpParseError(path, offset, line, record_index, "line-too-long")
    return value


def _content(value: bytes, *, path: Path, offset: int, line: int, record_index: int) -> bytes:
    if not value.endswith(b"\n"):
        raise DumpParseError(path, offset, line, record_index, "truncated-record")
    value = value[:-1]
    if value.endswith(b"\r"):
        value = value[:-1]
    elif b"\r" in value:
        raise DumpParseError(path, offset, line, record_index, "line-ending")
    return value


def _records(path: Path, profile) -> Iterator[OccurrenceInput]:
    width, height, shades = profile.width, profile.height, profile.native_shades
    if not all(type(value) is int and value > 0 for value in (width, height, shades)):
        raise ValueError("profile geometry and shade count must be positive integers")
    if shades > 10:
        raise ValueError("timestamped-text-v1 supports at most ten native shades")

    with path.open("rb") as handle:
        line = 1
        record_index = 0
        while True:
            offset = handle.tell()
            header_line = _line(handle, maximum=10, path=path, offset=offset, line=line, record_index=record_index)
            if not header_line:
                if record_index == 0:
                    raise DumpParseError(path, offset, line, record_index, "empty-dump")
                return
            header = _content(header_line, path=path, offset=offset, line=line, record_index=record_index)
            if not _HEADER.fullmatch(header):
                raise DumpParseError(path, offset, line, record_index, "timestamp")
            tick = int(header[2:], 16)
            line += 1
            pixels = bytearray()
            for _ in range(height):
                row_offset = handle.tell()
                row_line = _line(handle, maximum=width, path=path, offset=row_offset, line=line, record_index=record_index)
                if not row_line:
                    raise DumpParseError(path, row_offset, line, record_index, "truncated-record")
                row = _content(row_line, path=path, offset=row_offset, line=line, record_index=record_index)
                if not row:
                    raise DumpParseError(path, row_offset, line, record_index, "truncated-record")
                if row.startswith(b"0x"):
                    raise DumpParseError(path, row_offset, line, record_index, "truncated-record")
                if len(row) != width:
                    raise DumpParseError(path, row_offset, line, record_index, "row-width")
                if any(value < ord("0") or value >= ord("0") + shades for value in row):
                    raise DumpParseError(path, row_offset, line, record_index, "shade")
                pixels.extend(value - ord("0") for value in row)
                line += 1

            separator_offset = handle.tell()
            separator_line = _line(handle, maximum=width, path=path, offset=separator_offset, line=line, record_index=record_index)
            if not separator_line:
                raise DumpParseError(path, separator_offset, line, record_index, "truncated-record")
            if _content(separator_line, path=path, offset=separator_offset, line=line, record_index=record_index):
                raise DumpParseError(path, separator_offset, line, record_index, "missing-delimiter")
            line += 1
            yield OccurrenceInput(0, record_index, tick, None, "final-unknown", offset, handle.tell(), line - height - 2, bytes(pixels))
            record_index += 1


def read_dump(path: Path, profile) -> Iterator[OccurrenceInput]:
    """Yield strict, lossless occurrences with conservative duration semantics."""
    path = Path(path)
    pending: OccurrenceInput | None = None
    session = 0
    for current in _records(path, profile):
        current = replace(current, session=session)
        if pending is None:
            pending = current
            continue
        if current.original_tick >= pending.original_tick:
            yield replace(pending, duration_ticks=current.original_tick - pending.original_tick,
                          duration_status="observed-delta")
        else:
            yield replace(pending, duration_ticks=None, duration_status="discontinuity")
            session += 1
            current = replace(current, session=session)
        pending = current
    if pending is not None:
        yield pending
