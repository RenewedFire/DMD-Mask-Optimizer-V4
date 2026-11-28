"""Small, checksummed frame chunk files owned by the corpus store."""

from __future__ import annotations

import hashlib
import os
import struct
from pathlib import Path

MAGIC = b"DMDC1\0"


def write_record(handle, pixels: bytes) -> tuple[int, int]:
    """Append one framed payload and return its byte offset and raw length."""
    offset = handle.tell()
    handle.write(struct.pack(">I", len(pixels)))
    handle.write(pixels)
    return offset, len(pixels)


def finish(handle: object, path: Path) -> tuple[str, int]:
    handle.flush()
    os.fsync(handle.fileno())
    data = path.read_bytes()
    return hashlib.sha256(data).hexdigest(), len(data)


def verify_read(path: Path, checksum: str, offset: int, length: int) -> bytes:
    try:
        data = path.read_bytes()
    except OSError as error:
        raise ValueError(f"cannot read chunk {path}") from error
    if hashlib.sha256(data).hexdigest() != checksum:
        raise ValueError(f"chunk checksum mismatch: {path}")
    if not data.startswith(MAGIC) or offset < len(MAGIC) or offset + 4 + length > len(data):
        raise ValueError(f"invalid chunk record bounds: {path}")
    declared = struct.unpack(">I", data[offset:offset + 4])[0]
    if declared != length:
        raise ValueError(f"chunk record length mismatch: {path}")
    return data[offset + 4:offset + 4 + length]
