"""SQLite metadata plus append-only, verified frame chunks."""

from __future__ import annotations

import hashlib
import json
import math
import os
import shutil
import sqlite3
import struct
import uuid
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable, Iterator

from dmd_optimizer.capture.text_dump import OccurrenceInput
from . import chunks

_SCHEMA = Path(__file__).parents[3] / "schemas" / "corpus-v1.sql"
_PAYLOAD_LIMIT = 4 * 1024 * 1024


class CorpusError(ValueError):
    pass


@dataclass(frozen=True)
class Capture:
    source_sha256: str; source_uri: str; producer: str; producer_version: str | None; configuration: dict; complete: bool
    width: int; height: int; native_shades: int; encoding: str; normalization: str; tick_unit: str | None
    timestamp_semantics: dict; rom_sha256: str; profile_sha256: str


@dataclass(frozen=True)
class Revision:
    digest: str; parent_digest: str | None; capture_count: int; occurrence_count: int; unique_frame_count: int; complete: bool


@dataclass(frozen=True)
class StoredOccurrence:
    capture_id: str; frame_id: str; session: int; index: int; original_tick: int; duration_ticks: int | None
    duration_status: str; offset: int; end_offset: int; line: int


@dataclass(frozen=True)
class CaptureMetadata:
    capture_id: str
    ordinal: int
    source: Capture


def _canonical(value: object) -> bytes:
    def valid(item: object) -> bool:
        if item is None or isinstance(item, (str, bool, int)):
            return True
        if isinstance(item, float):
            return math.isfinite(item)
        if isinstance(item, list):
            return all(valid(child) for child in item)
        if isinstance(item, dict):
            return all(isinstance(key, str) and valid(child) for key, child in item.items())
        return False
    if not valid(value):
        raise CorpusError("provenance must use string keys and finite JSON values")
    try:
        text = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)
    except (TypeError, ValueError) as error:
        raise CorpusError("provenance must be JSON-serializable with finite values") from error
    return text.encode("utf-8")


def _hex(value: str, name: str) -> None:
    if not isinstance(value, str) or len(value) != 64 or any(ch not in "0123456789abcdef" for ch in value):
        raise CorpusError(f"{name} must be a lowercase SHA-256 hex digest")


def _frame_input(source: Capture, pixels: bytes) -> bytes:
    return _canonical([source.width, source.height, source.native_shades, source.encoding, source.normalization]) + b"\0" + pixels


def _lookup_digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _frame_id(data: bytes) -> str:
    return hashlib.sha512(data).hexdigest()


def _layout(project: Path) -> tuple[Path, Path, Path]:
    project = Path(project).resolve()
    project.mkdir(parents=True, exist_ok=True)
    chunks_dir, staging = project / "chunks", project / "staging"
    chunks_dir.mkdir(exist_ok=True); staging.mkdir(exist_ok=True)
    return project / "corpus.sqlite3", chunks_dir, staging


def _connect(project: Path) -> sqlite3.Connection:
    database, _, _ = _layout(project)
    existed = database.exists() and database.stat().st_size > 0
    conn = sqlite3.connect(database, timeout=5, isolation_level=None)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON"); conn.execute("PRAGMA journal_mode=DELETE"); conn.execute("PRAGMA synchronous=FULL"); conn.execute("PRAGMA busy_timeout=5000")
    if existed:
        tables = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        expected = {"project", "chunks", "frames", "captures", "occurrences", "revisions", "revision_captures"}
        if tables - expected:
            conn.close()
            raise CorpusError("refusing unrelated database")
    conn.executescript(_SCHEMA.read_text(encoding="utf-8"))
    return conn


def _connect_read_only(project: Path) -> sqlite3.Connection:
    project = Path(project).resolve()
    database = project / "corpus.sqlite3"
    if not database.is_file():
        raise CorpusError(f"corpus does not exist: {project}")
    conn = sqlite3.connect(f"file:{database.as_posix()}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    return conn


def _validate_source(source: Capture) -> bytes:
    for value, name in ((source.source_sha256, "source"), (source.rom_sha256, "ROM"), (source.profile_sha256, "profile")):
        _hex(value, name)
    if not all(isinstance(value, int) and value > 0 for value in (source.width, source.height, source.native_shades)):
        raise CorpusError("geometry and native shades must be positive integers")
    if not isinstance(source.complete, bool) or not all(isinstance(x, str) and x for x in (source.source_uri, source.producer, source.encoding, source.normalization)):
        raise CorpusError("invalid capture provenance")
    return _canonical(asdict(source))


def _validate_occurrence(item: OccurrenceInput, source: Capture, expected_index: int, expected_session: int) -> None:
    if item.index != expected_index or (expected_index == 0 and item.session != 0) or (expected_index > 0 and item.session not in (expected_session, expected_session + 1)):
        raise CorpusError("occurrence indices or sessions are not contiguous")
    if len(item.native_pixels) != source.width * source.height or any(value >= source.native_shades for value in item.native_pixels):
        raise CorpusError("native pixels do not match capture geometry or shade range")
    if any(type(value) is not int or value < 0 for value in (item.original_tick, item.offset, item.end_offset, item.line)) or item.end_offset < item.offset:
        raise CorpusError("invalid occurrence positions")
    if item.duration_status not in {"observed-delta", "discontinuity", "final-unknown"}:
        raise CorpusError("unsupported duration status")
    if item.duration_ticks is not None and (type(item.duration_ticks) is not int or item.duration_ticks < 0):
        raise CorpusError("invalid duration ticks")
    if item.duration_status == "observed-delta" and item.duration_ticks is None:
        raise CorpusError("observed delta requires a duration")
    if item.duration_status != "observed-delta" and item.duration_ticks is not None:
        raise CorpusError("unknown/discontinuity durations must be null")


def _revision(conn: sqlite3.Connection, digest: str) -> Revision:
    row = conn.execute("SELECT digest,parent_digest,complete FROM revisions WHERE digest=?", (digest,)).fetchone()
    if row is None: raise CorpusError(f"unknown revision: {digest}")
    counts = conn.execute("SELECT COUNT(*) captures, COALESCE(SUM((SELECT COUNT(*) FROM occurrences o WHERE o.capture_id=rc.capture_id)),0) occurrences, COALESCE((SELECT COUNT(DISTINCT o.frame_id) FROM revision_captures r2 JOIN occurrences o ON o.capture_id=r2.capture_id WHERE r2.revision_digest=?),0) frames FROM revision_captures rc WHERE rc.revision_digest=?", (digest, digest)).fetchone()
    return Revision(row["digest"], row["parent_digest"], counts["captures"], counts["occurrences"], counts["frames"], bool(row["complete"]))


def _current(conn: sqlite3.Connection) -> str | None:
    row = conn.execute("SELECT value FROM project WHERE key='current_revision'").fetchone()
    return None if row is None else row[0]


def append_capture(project: Path, source: Capture, occurrences: Iterable[OccurrenceInput]) -> Revision:
    provenance = _validate_source(source)
    database, chunks_dir, staging = _layout(project)
    conn = _connect(project)
    try:
        conn.execute("BEGIN IMMEDIATE")
        identity = {row[0]: row[1] for row in conn.execute("SELECT key,value FROM project WHERE key IN ('schema_version','rom_sha256','profile_sha256')")}
        if identity:
            if identity.get("schema_version") != "1": raise CorpusError("unsupported corpus schema")
            if identity.get("rom_sha256") != source.rom_sha256: raise CorpusError("ROM identity does not match corpus")
            if identity.get("profile_sha256") != source.profile_sha256: raise CorpusError("profile identity does not match corpus")
        conn.execute("CREATE TEMP TABLE staged (n INTEGER PRIMARY KEY, frame_id TEXT, session INTEGER, tick INTEGER, duration INTEGER, status TEXT, start INTEGER, ending INTEGER, line INTEGER)")
        pending: dict[str, tuple[str, str, int, int, int, int, str, str, bytes]] = {}
        validated_existing: set[str] = set()
        verified_chunks: dict[str, bytes] = {}
        completed_chunks: list[tuple[str, Path, str, int]] = []
        hasher = hashlib.sha256(provenance + b"\n")
        expected_session = 0; count = 0; payload = 0
        handle = None
        chunk_temp: Path | None = None
        chunk_id: str | None = None
        chunk_payload = 0

        def close_chunk() -> None:
            nonlocal handle, chunk_temp, chunk_id, chunk_payload
            if handle is None or chunk_temp is None or chunk_id is None:
                return
            checksum, size = chunks.finish(handle, chunk_temp)
            handle.close()
            destination = chunks_dir / f"{chunk_id}.bin"
            os.replace(chunk_temp, destination)
            completed_chunks.append((chunk_id, destination, checksum, size))
            handle = chunk_temp = chunk_id = None
            chunk_payload = 0

        try:
            for item in occurrences:
                _validate_occurrence(item, source, count, expected_session)
                expected_session = item.session
                encoded = _frame_input(source, item.native_pixels); lookup, frame_id = _lookup_digest(encoded), _frame_id(encoded)
                existing = conn.execute("SELECT frame_id FROM frames WHERE frame_id=?", (frame_id,)).fetchone()
                if frame_id in pending and pending[frame_id][-1] != item.native_pixels:
                    raise CorpusError("stable frame digest collision")
                if existing is not None and frame_id not in validated_existing:
                    row = conn.execute("SELECT f.*,c.filename,c.sha256 FROM frames f JOIN chunks c ON c.chunk_id=f.chunk_id WHERE f.frame_id=?", (frame_id,)).fetchone()
                    try:
                        data = verified_chunks.get(row["filename"])
                        if data is None:
                            data = (chunks_dir / row["filename"]).read_bytes()
                            if hashlib.sha256(data).hexdigest() != row["sha256"] or not data.startswith(chunks.MAGIC):
                                raise ValueError("chunk checksum or magic mismatch")
                            verified_chunks[row["filename"]] = data
                        offset, length = row["offset"], row["length"]
                        if offset < len(chunks.MAGIC) or offset + 4 + length > len(data) or struct.unpack(">I", data[offset:offset + 4])[0] != length:
                            raise ValueError("chunk record bounds mismatch")
                        prior = data[offset + 4:offset + 4 + length]
                    except ValueError as error:
                        raise CorpusError(f"chunk corruption for existing frame {frame_id}") from error
                    if (row["width"], row["height"], row["native_shades"], row["encoding"], row["normalization"], prior) != (source.width, source.height, source.native_shades, source.encoding, source.normalization, item.native_pixels):
                        raise CorpusError("stable frame digest collision")
                    validated_existing.add(frame_id)
                if existing is None and frame_id not in pending:
                    if handle is None or (chunk_payload and chunk_payload + len(item.native_pixels) > _PAYLOAD_LIMIT):
                        close_chunk()
                        chunk_id = uuid.uuid4().hex
                        chunk_temp = staging / f"{chunk_id}.tmp"
                        handle = chunk_temp.open("wb")
                        handle.write(chunks.MAGIC)
                    offset, length = chunks.write_record(handle, item.native_pixels); payload += length
                    chunk_payload += length
                    pending[frame_id] = (lookup, chunk_id, offset, length, source.width, source.height, source.encoding, source.normalization, item.native_pixels)
                hasher.update(_canonical([frame_id, item.session, item.index, item.original_tick, item.duration_ticks, item.duration_status, item.offset, item.end_offset, item.line]) + b"\n")
                conn.execute("INSERT INTO staged VALUES (?,?,?,?,?,?,?,?,?)", (item.index, frame_id, item.session, item.original_tick, item.duration_ticks, item.duration_status, item.offset, item.end_offset, item.line))
                count += 1
            close_chunk()
        except Exception:
            if handle is not None:
                handle.close()
            raise
        capture_id = hasher.hexdigest()
        old = conn.execute("SELECT 1 FROM captures WHERE capture_id=?", (capture_id,)).fetchone()
        parent = _current(conn)
        if old:
            conn.execute("ROLLBACK")
            return read_revision(project, parent)
        if pending:
            for pending_chunk_id, final, checksum, size in completed_chunks:
                conn.execute("INSERT INTO chunks VALUES (?,?,?,?)", (pending_chunk_id, final.name, checksum, size))
            for frame_id, (lookup, pending_chunk_id, offset, length, width, height, encoding, normalization, _pixels) in pending.items():
                collision = conn.execute("SELECT frame_id FROM frames WHERE frame_id=?", (frame_id,)).fetchone()
                if collision: raise CorpusError("stable frame digest collision")
                conn.execute("INSERT INTO frames VALUES (?,?,?,?,?,?,?,?,?,?)", (frame_id, lookup, width, height, source.native_shades, encoding, normalization, pending_chunk_id, offset, length))
        conn.execute("INSERT INTO captures VALUES (?,?,?)", (capture_id, provenance.decode("utf-8"), int(source.complete)))
        conn.execute("INSERT INTO occurrences SELECT ?,n,frame_id,session,tick,duration,status,start,ending,line FROM staged", (capture_id,))
        members = [] if parent is None else [r[0] for r in conn.execute("SELECT capture_id FROM revision_captures WHERE revision_digest=? ORDER BY ordinal", (parent,))]
        members.append(capture_id)
        digest = hashlib.sha256(_canonical([1, source.rom_sha256, source.profile_sha256, members])).hexdigest()
        complete = all(bool(r[0]) for r in conn.execute("SELECT complete FROM captures WHERE capture_id IN (%s)" % ",".join("?" * len(members)), members))
        conn.execute("INSERT INTO revisions VALUES (?,?,?)", (digest, parent, int(complete)))
        conn.executemany("INSERT INTO revision_captures VALUES (?,?,?)", [(digest, member, ordinal) for ordinal, member in enumerate(members)])
        for key, value in (("schema_version", "1"), ("rom_sha256", source.rom_sha256), ("profile_sha256", source.profile_sha256), ("current_revision", digest)):
            conn.execute("INSERT INTO project VALUES (?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value", (key, value))
        conn.execute("COMMIT")
        return read_revision(project, digest)
    except Exception:
        if conn.in_transaction: conn.execute("ROLLBACK")
        raise
    finally:
        conn.close()


def read_revision(project: Path, digest: str | None = None) -> Revision:
    conn = _connect_read_only(project)
    try:
        chosen = digest or _current(conn)
        if chosen is None: raise CorpusError("corpus has no revisions")
        return _revision(conn, chosen)
    finally: conn.close()


def read_capture_metadata(project: Path, revision_digest: str) -> tuple[CaptureMetadata, ...]:
    """Read revision provenance without creating corpus files or directories."""
    conn = _connect_read_only(project)
    try:
        _revision(conn, revision_digest)
        rows = conn.execute(
            "SELECT rc.capture_id,rc.ordinal,c.provenance_json FROM revision_captures rc "
            "JOIN captures c ON c.capture_id=rc.capture_id "
            "WHERE rc.revision_digest=? ORDER BY rc.ordinal", (revision_digest,)
        )
        result = []
        for row in rows:
            try:
                source = Capture(**json.loads(row["provenance_json"]))
                _validate_source(source)
            except (TypeError, ValueError, json.JSONDecodeError) as error:
                raise CorpusError(f"invalid capture provenance for {row['capture_id']}") from error
            result.append(CaptureMetadata(row["capture_id"], row["ordinal"], source))
        return tuple(result)
    finally:
        conn.close()


def iter_occurrences(project: Path, revision_digest: str) -> Iterator[StoredOccurrence]:
    conn = _connect_read_only(project)
    try:
        _revision(conn, revision_digest)
        rows = conn.execute("SELECT rc.capture_id,o.frame_id,o.session,o.occurrence_index,o.original_tick,o.duration_ticks,o.duration_status,o.offset,o.end_offset,o.line FROM revision_captures rc JOIN occurrences o ON o.capture_id=rc.capture_id WHERE rc.revision_digest=? ORDER BY rc.ordinal,o.occurrence_index", (revision_digest,))
        for row in rows: yield StoredOccurrence(row[0], row[1], row[2], row[3], row[4], row[5], row[6], row[7], row[8], row[9])
    finally: conn.close()


def read_frame(project: Path, frame_id: str) -> bytes:
    conn = _connect_read_only(project)
    try:
        row = conn.execute("SELECT f.*,c.filename,c.sha256 FROM frames f JOIN chunks c ON c.chunk_id=f.chunk_id WHERE f.frame_id=?", (frame_id,)).fetchone()
        if row is None: raise CorpusError(f"unknown frame: {frame_id}")
        try: pixels = chunks.verify_read(Path(project) / "chunks" / row["filename"], row["sha256"], row["offset"], row["length"])
        except ValueError as error: raise CorpusError(f"chunk corruption for frame {frame_id}: {error}") from error
        data = _canonical([row["width"], row["height"], row["native_shades"], row["encoding"], row["normalization"]]) + b"\0" + pixels
        if _frame_id(data) != frame_id: raise CorpusError(f"frame identity mismatch: {frame_id}")
        return pixels
    finally: conn.close()


def read_frames(project: Path, frame_ids: Iterable[str]) -> dict[str, bytes]:
    """Read a bounded set of unique frames while verifying each chunk once."""
    wanted = tuple(dict.fromkeys(frame_ids))
    if not wanted:
        return {}
    conn = _connect_read_only(project)
    try:
        marks = ",".join("?" for _ in wanted)
        rows = tuple(conn.execute(
            f"SELECT f.*,c.filename,c.sha256 FROM frames f JOIN chunks c ON c.chunk_id=f.chunk_id WHERE f.frame_id IN ({marks})",
            wanted,
        ))
    finally:
        conn.close()
    if len(rows) != len(wanted):
        found = {row["frame_id"] for row in rows}
        raise CorpusError(f"unknown frame: {next(item for item in wanted if item not in found)}")
    blobs: dict[str, bytes] = {}
    result: dict[str, bytes] = {}
    for row in rows:
        try:
            data = blobs.get(row["filename"])
            if data is None:
                data = (Path(project) / "chunks" / row["filename"]).read_bytes()
                if hashlib.sha256(data).hexdigest() != row["sha256"] or not data.startswith(chunks.MAGIC):
                    raise ValueError("chunk checksum or magic mismatch")
                blobs[row["filename"]] = data
            offset, length = row["offset"], row["length"]
            if offset < len(chunks.MAGIC) or offset + 4 + length > len(data) or struct.unpack(">I", data[offset:offset + 4])[0] != length:
                raise ValueError("chunk record bounds mismatch")
            pixels = data[offset + 4:offset + 4 + length]
        except (OSError, ValueError) as error:
            raise CorpusError(f"chunk corruption for frame {row['frame_id']}") from error
        encoded = _canonical([row["width"], row["height"], row["native_shades"], row["encoding"], row["normalization"]]) + b"\0" + pixels
        if _frame_id(encoded) != row["frame_id"]:
            raise CorpusError(f"frame identity mismatch: {row['frame_id']}")
        result[row["frame_id"]] = pixels
    return result


def recover(project: Path) -> None:
    conn = _connect(project)
    try:
        conn.execute("BEGIN IMMEDIATE")
        if conn.execute("PRAGMA integrity_check").fetchone()[0] != "ok": raise CorpusError("SQLite integrity check failed")
        _, chunks_dir, staging = _layout(project)
        referenced = {row[0] for row in conn.execute("SELECT filename FROM chunks")}
        for row in conn.execute("SELECT frame_id FROM frames"): read_frame(project, row[0])
        orphan_root = Path(project) / "orphans" / uuid.uuid4().hex; orphan_root.mkdir(parents=True)
        for directory in (chunks_dir, staging):
            for child in directory.iterdir():
                if child.is_file() and (directory == staging or child.name not in referenced): shutil.move(str(child), orphan_root / child.name)
        conn.execute("COMMIT")
    except Exception:
        if conn.in_transaction: conn.execute("ROLLBACK")
        raise
    finally: conn.close()
