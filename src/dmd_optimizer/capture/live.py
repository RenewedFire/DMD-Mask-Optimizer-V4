"""Lossless parser and comparator for the native PinMAME capture trace."""

from __future__ import annotations

import hashlib
import json
import struct
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Iterable, Iterator

from .text_dump import OccurrenceInput
from dmd_optimizer.rom.audit import AuditResult

_MAGIC = b"DMDLIVE1"
_MAX_METADATA = 64 * 1024
_FIXED = struct.Struct("<QQHHHI")


class CaptureError(ValueError):
    pass


@dataclass(frozen=True)
class TraceRecord:
    sequence: int
    tick: int
    pixels: bytes


@dataclass(frozen=True)
class InputEvent:
    at_ms: int
    switch: int
    closed: bool


@dataclass(frozen=True)
class CaptureRequest:
    audit: AuditResult
    profile: object
    worker: Path
    runtime_dir: Path
    settings: dict
    input_schedule: tuple[InputEvent, ...]
    stop_after_ms: int
    timeout_ms: int


@dataclass(frozen=True)
class ParityResult:
    passed: bool
    occurrence_count: int
    first_divergence: dict | None
    capture_sha256: str
    consumer_sha256: str
    session_id: str


def _canonical(value: object) -> bytes:
    try:
        return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode("utf-8")
    except (TypeError, ValueError) as error:
        raise CaptureError("trace metadata must be finite JSON") from error


def _metadata(metadata: dict) -> tuple[int, int, int]:
    required = ("session_id", "stream_role", "rom_sha256", "profile_sha256", "build_sha256", "width", "height", "native_shades", "encoding", "tick_unit", "hook_location")
    if not isinstance(metadata, dict) or any(key not in metadata for key in required):
        raise CaptureError("trace metadata is missing required fields")
    if metadata["stream_role"] not in {"capture", "consumer"}:
        raise CaptureError("trace stream role is unsupported")
    if metadata["encoding"] != "native-u8":
        raise CaptureError("luminance or unsupported trace encoding")
    if not all(type(metadata[key]) is int and metadata[key] > 0 for key in ("width", "height", "native_shades")):
        raise CaptureError("invalid trace geometry")
    if not isinstance(metadata["tick_unit"], (str, type(None))):
        raise CaptureError("invalid native clock unit")
    return metadata["width"], metadata["height"], metadata["native_shades"]


def write_trace(path: Path, metadata: dict, records: Iterable[TraceRecord]) -> None:
    """Write a test/native-worker trace with exact native bytes and ticks."""
    width, height, shades = _metadata(metadata)
    encoded_metadata = _canonical(metadata)
    if len(encoded_metadata) > _MAX_METADATA:
        raise CaptureError("trace metadata exceeds 64 KiB")
    path = Path(path)
    with path.open("wb") as output:
        output.write(_MAGIC); output.write(struct.pack("<I", len(encoded_metadata))); output.write(encoded_metadata)
        expected = 0
        for record in records:
            if record.sequence != expected or record.tick < 0:
                raise CaptureError("trace sequence or native tick is invalid")
            if len(record.pixels) != width * height or any(pixel >= shades for pixel in record.pixels):
                raise CaptureError("trace pixels do not match native geometry")
            body = _FIXED.pack(record.sequence, record.tick, width, height, shades, len(record.pixels)) + record.pixels
            output.write(struct.pack("<I", len(body))); output.write(body)
            expected += 1


def _load(path: Path) -> tuple[dict, list[tuple[TraceRecord, int, int]]]:
    path = Path(path)
    try:
        data = path.read_bytes()
    except OSError as error:
        raise CaptureError(f"cannot read trace {path}") from error
    if len(data) < len(_MAGIC) + 4 or data[:len(_MAGIC)] != _MAGIC:
        raise CaptureError(f"invalid trace magic: {path}")
    size = struct.unpack_from("<I", data, len(_MAGIC))[0]
    start = len(_MAGIC) + 4
    if size > _MAX_METADATA or start + size > len(data):
        raise CaptureError(f"invalid trace metadata bounds: {path}")
    try:
        metadata = json.loads(data[start:start + size].decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise CaptureError(f"invalid trace metadata: {path}") from error
    width, height, shades = _metadata(metadata)
    offset = start + size; records = []; expected = 0
    while offset < len(data):
        record_start = offset
        if offset + 4 > len(data): raise CaptureError(f"truncated trace record length: {path}")
        length = struct.unpack_from("<I", data, offset)[0]; offset += 4
        if length < _FIXED.size or offset + length > len(data): raise CaptureError(f"truncated trace record: {path}")
        sequence, tick, w, h, native_shades, payload_length = _FIXED.unpack_from(data, offset)
        if w != width or h != height or native_shades != shades or payload_length != length - _FIXED.size:
            raise CaptureError(f"trace record metadata mismatch: {path}")
        pixels = data[offset + _FIXED.size:offset + length]
        if sequence != expected or any(pixel >= shades for pixel in pixels):
            raise CaptureError(f"invalid trace sequence or native pixel: {path}")
        records.append((TraceRecord(sequence, tick, pixels), record_start, offset + length))
        offset += length; expected += 1
    return metadata, records


def _digest(path: Path) -> str:
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def compare_traces(capture_path: Path, consumer_path: Path) -> ParityResult:
    """Require exact same-run native records at separate capture and consumer hooks."""
    capture_meta, capture_records = _load(capture_path)
    consumer_meta, consumer_records = _load(consumer_path)
    if capture_meta["stream_role"] != "capture" or consumer_meta["stream_role"] != "consumer":
        raise CaptureError("trace roles must be capture then consumer")
    compare_keys = set(capture_meta) | set(consumer_meta)
    compare_keys -= {"stream_role", "hook_location"}
    for key in sorted(compare_keys):
        if capture_meta.get(key) != consumer_meta.get(key):
            raise CaptureError(f"same-run trace metadata differs at {key}")
    for index, (left, right) in enumerate(zip(capture_records, consumer_records)):
        if left[0] != right[0]:
            raise CaptureError(f"trace divergence at record {index}")
    if len(capture_records) != len(consumer_records):
        raise CaptureError("trace occurrence count differs")
    return ParityResult(True, len(capture_records), None, _digest(capture_path), _digest(consumer_path), capture_meta["session_id"])


def read_trace(path: Path) -> Iterator[OccurrenceInput]:
    """Yield Task 4-compatible occurrences while retaining resets and repeats."""
    _metadata_value, rows = _load(path)
    pending: OccurrenceInput | None = None; session = 0
    for record, offset, end_offset in rows:
        current = OccurrenceInput(session, record.sequence, record.tick, None, "final-unknown", offset, end_offset, record.sequence + 1, record.pixels)
        if pending is None:
            pending = current; continue
        if current.original_tick >= pending.original_tick:
            yield replace(pending, duration_ticks=current.original_tick - pending.original_tick, duration_status="observed-delta")
        else:
            yield replace(pending, duration_ticks=None, duration_status="discontinuity")
            session += 1; current = replace(current, session=session)
        pending = current
    if pending is not None: yield pending


def _profile_digest(profile: object) -> str:
    return profile if isinstance(profile, str) else getattr(profile, "profile_sha256", "")


def _owned_child(root: Path, value: str) -> Path:
    candidate = (root / value).resolve()
    if candidate.parent != root.resolve() or candidate.suffix != ".bin":
        raise CaptureError("completion trace path escapes the owned output directory")
    return candidate


def capture(session: CaptureRequest) -> Iterator[OccurrenceInput]:
    """Consume only a completed, parity-validated native worker run."""
    if session.stop_after_ms <= 0 or session.timeout_ms < session.stop_after_ms:
        raise CaptureError("invalid capture time limits")
    previous = -1
    for event in session.input_schedule:
        if type(event.at_ms) is not int or type(event.switch) is not int or not isinstance(event.closed, bool) or event.at_ms < previous or event.at_ms > session.stop_after_ms:
            raise CaptureError("invalid ordered input schedule")
        previous = event.at_ms
    output = Path(session.runtime_dir).resolve()
    manifest_path = output / "completion.json"
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise CaptureError(f"missing or invalid completion manifest: {manifest_path}") from error
    if not isinstance(manifest, dict) or manifest.get("complete") is not True:
        raise CaptureError("native worker run is incomplete")
    required = ("session_id", "capture_trace", "consumer_trace", "capture_sha256", "consumer_sha256", "rom_content_sha256", "profile_sha256")
    if any(not isinstance(manifest.get(key), str) or not manifest[key] for key in required):
        raise CaptureError("completion manifest is missing identity fields")
    if manifest["rom_content_sha256"] != session.audit.content_sha256 or manifest["profile_sha256"] != _profile_digest(session.profile):
        raise CaptureError("completion manifest does not bind the requested audit/profile")
    capture_path = _owned_child(output, manifest["capture_trace"])
    consumer_path = _owned_child(output, manifest["consumer_trace"])
    if _digest(capture_path) != manifest["capture_sha256"] or _digest(consumer_path) != manifest["consumer_sha256"]:
        raise CaptureError("completion manifest trace digest mismatch")
    parity = compare_traces(capture_path, consumer_path)
    if parity.session_id != manifest["session_id"]:
        raise CaptureError("trace session does not match completion manifest")
    yield from read_trace(capture_path)
