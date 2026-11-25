"""Replay the Twister normal-comparison profile against an isolated Serum 2.1.0 DLL."""

import hashlib
import io
import json
import os
import shutil
import struct
import subprocess
import uuid
import zipfile
import zlib
from collections.abc import Iterable, Iterator
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path

from dmd_optimizer.adapters.editor import ProjectFiles, _DECODER_SHA256
from scripts.lock_profile import Profile

ROOT = Path(__file__).resolve().parents[3]
HEADER = struct.Struct("<4sBBH")
OBSERVATION = struct.Struct("<6I")
PIXELS = 4096
NO_FRAME = 0xffffffff
MAX_ARCHIVE = 256 * 1024 * 1024


class IncompatibleExport(ValueError):
    """The runtime file does not fit the pinned native decoder layout."""


@dataclass(frozen=True)
class Frame:
    pixels: bytes


@dataclass(frozen=True)
class AdvanceTime:
    milliseconds: int


@dataclass(frozen=True)
class Reset:
    pass


ReplayEvent = Frame | AdvanceTime | Reset


@dataclass(frozen=True)
class Output:
    result: int
    flags: int
    trigger: int
    rotation_timer: int
    width: int
    pixels_sha256: str | None


@dataclass(frozen=True)
class Match:
    event: str
    reference: str | None
    reference_origin: str | None
    output: Output | None


def compared_bytes(frame: bytes, ignore: bytes | None) -> bytes:
    if len(frame) != PIXELS or max(frame) > 3:
        raise ValueError("expected 4096 raw four-shade pixels")
    if ignore is None:
        return bytes(frame)
    if len(ignore) != PIXELS or max(ignore) > 1:
        raise ValueError("expected 4096 binary ignore pixels")
    return bytes(value for value, masked in zip(frame, ignore) if not masked)


def _package(project, profile):
    if (profile.rom_revision, profile.width, profile.height, profile.native_shades) != ("twst_405", 128, 32, 4):
        raise ValueError("unsupported oracle profile")
    if project.runtime_export is None or project.runtime_export.name != "twst_405.cRZ":
        raise ValueError("expected twst_405.cRZ runtime export")
    manifest = json.loads(project.manifest_path.read_bytes())
    if manifest["runtime_export"] != project.runtime_export.name or project.runtime_export.stat().st_size > MAX_ARCHIVE:
        raise ValueError("invalid runtime export")
    data = project.runtime_export.read_bytes()
    digest = hashlib.sha256(data).hexdigest()
    if [item["sha256"] for item in manifest["files"] if item["path"] == manifest["runtime_export"]] != [digest]:
        raise ValueError("runtime export SHA-256 mismatch")
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        if archive.namelist() != ["twst_405.cRom"] or archive.infolist()[0].file_size > MAX_ARCHIVE:
            raise IncompatibleExport("expected one bounded twst_405.cRom")
        crom = archive.read("twst_405.cRom")
    if len(crom) < 102:
        raise IncompatibleExport("truncated cROM header")
    version, width, height, width_x, height_x, count, shades, masks, sprites, backgrounds = struct.unpack_from("<9IH", crom, 64)
    if ((version, width, height, width_x, height_x, shades) != (80, 128, 32, 256, 64, 4)
            or not 1 <= count <= 65535 or masks > 64 or sprites or backgrounds):
        raise IncompatibleExport("unsupported cROM dimensions, counts or format")
    start = 102 + 4 * count
    shape = crom[start:start + count]
    slots = crom[start + count:start + 2 * count]
    if len(slots) != count or any(shape) or any(s != 255 and s >= masks for s in slots):
        raise IncompatibleExport("invalid shape or slot table with Serum 2.1.0 hashes at byte 102")
    # Size of Serum_LoadNewFile's serialized arrays for this sprite-free,
    # background-free profile. The editor can append six shadow bytes per set.
    plane_pixels = PIXELS + width_x * height_x
    per_reference = (6 + 1 + 4 * plane_pixels + 2 * 2 * 32 * shades
                     + 32 + 1 + 2 * 2 * 64 * 4 + 4 + 2 * 32 * 4 + 2)
    base_size = 102 + masks * PIXELS + count * per_reference
    if len(crom) not in (base_size, base_size + count * 32 * 6):
        raise IncompatibleExport("file length differs from Serum 2.1.0 array layout")
    refs = manifest["references"]
    ids = tuple(r["id"] for r in refs)
    if (len(refs) != count or [r["ordinal"] for r in refs] != list(range(count))
            or any(not isinstance(id_, str) or not id_ for id_ in ids) or len(set(ids)) != count):
        raise ValueError("invalid ordinal to reference mapping")
    return data, ids, slots


class Worker:
    """Own one synchronous stream, a private loader directory and one child process."""

    def __init__(self, project: ProjectFiles, profile: Profile, *, instrument=True):
        data, self.ids, self.slots = _package(project, profile)
        self.last_unmasked = None
        self.project_digest = hashlib.sha256(data).digest()
        self.instrument = instrument
        dll_path = os.environ.get("DMD_EDITOR_DECODER_PATH")
        if not dll_path:
            raise ValueError("set DMD_EDITOR_DECODER_PATH to the source-tree Serum 2.1.0 DLL")
        dll = Path(dll_path).resolve(strict=True)
        if (profile.components["bundled decoder"]["sha256"] != _DECODER_SHA256
                or profile.components["bundled decoder"]["source_tree_binary_version"] != "2.1.0"):
            raise ValueError("source-tree Serum 2.1.0 profile SHA-256 or version mismatch")
        worker = Path(os.getenv("DMD_SERUM_WORKER", ROOT / "artifacts/oracle/serum_worker.exe")).resolve(strict=True)
        self.folder = ROOT / "artifacts" / "oracle" / uuid.uuid4().hex
        (self.folder / "twst_405").mkdir(parents=True)
        self.process = None
        self.io = ThreadPoolExecutor(max_workers=1)
        try:
            (self.folder / "twst_405/twst_405.cRZ").write_bytes(data)
            # Stage verified bytes so the file loaded in the child is the one checked.
            local_dll = self.folder / "serum64.dll"
            shutil.copyfile(dll, local_dll)
            if hashlib.sha256(local_dll.read_bytes()).hexdigest() != _DECODER_SHA256:
                raise ValueError("staged decoder SHA-256 mismatch")
            self.process = subprocess.Popen([worker, local_dll, self.folder, "observe" if instrument else "production"],
                                            stdin=subprocess.PIPE, stdout=subprocess.PIPE, cwd=self.folder,
                                            creationflags=subprocess.CREATE_NO_WINDOW)
            self._exchange(4, b"", 5)
        except BaseException:
            self.close(force=True)
            raise

    def _exchange(self, operation, payload, timeout):
        def transact():
            if operation != 4:
                self.process.stdin.write(HEADER.pack(b"DMDW", 1, operation, len(payload)) + payload)
                self.process.stdin.flush()
            header = self.process.stdout.read(HEADER.size)
            if len(header) != HEADER.size:
                raise RuntimeError(f"Serum worker exited during operation {operation}")
            magic, version, op, length = HEADER.unpack(header)
            lengths = (0,) if op in (3, 4) else (OBSERVATION.size, OBSERVATION.size + 2 * PIXELS)
            if (magic, version, op) != (b"DMDW", 1, operation) or length not in lengths:
                raise RuntimeError("invalid Serum worker response")
            response = self.process.stdout.read(length)
            if len(response) != length:
                raise RuntimeError("truncated Serum worker response")
            return response

        try:
            return self.io.submit(transact).result(timeout=timeout)
        except BaseException:
            if self.process.poll() is None:
                self.process.kill()
            self.process.wait()
            raise

    def request(self, event: Frame | AdvanceTime, *, timeout=None) -> Match:
        if isinstance(event, Frame):
            if not isinstance(event.pixels, bytes):
                raise ValueError("frame pixels must be bytes")
            payload = compared_bytes(event.pixels, None)
            operation, name, delay = 1, "frame", 0
        elif isinstance(event, AdvanceTime):
            if type(event.milliseconds) is not int or not 0 <= event.milliseconds <= 60000:
                raise ValueError("advance must be 0 through 60000 milliseconds")
            payload = struct.pack("<I", event.milliseconds)
            operation, name, delay = 2, "advance-time", event.milliseconds / 1000
        else:
            raise ValueError("unknown replay event")
        raw = self._exchange(operation, payload, timeout if timeout is not None else 5 + delay)
        result, flags, trigger, timer, ordinal, width = OBSERVATION.unpack_from(raw)
        rgb = raw[OBSERVATION.size:]
        output = Output(result, flags, trigger, timer, width, hashlib.sha256(rgb).hexdigest() if rgb else None)
        reference = origin = None
        if self.instrument and operation == 1:
            crc = zlib.crc32(payload)
            if ordinal != NO_FRAME:
                if ordinal >= len(self.ids):
                    raise RuntimeError(f"native reference ordinal out of range: {ordinal}")
                reference, origin = self.ids[ordinal], "frameID"
                self.last_unmasked = (crc, reference) if self.slots[ordinal] == 255 else None
            elif result == NO_FRAME and self.last_unmasked and crc == self.last_unmasked[0]:
                # 2.1.0 reports the same sentinel for unknown and unchanged. A
                # normal, unmasked previous winner checks its full CRC first.
                reference, origin = self.last_unmasked[1], "unchanged-crc"
        return Match(name, reference, origin, output)

    def close(self, *, force=False):
        try:
            if self.process is not None and self.process.poll() is None:
                if force:
                    self.process.kill()
                else:
                    self._exchange(3, b"", 3)
                self.process.wait(timeout=3)
        finally:
            if self.process is not None:
                if self.process.poll() is None:
                    self.process.kill()
                    self.process.wait()
                self.process.stdin.close()
                self.process.stdout.close()
            self.io.shutdown()
            shutil.rmtree(self.folder)

    def __enter__(self):
        return self

    def __exit__(self, kind, value, trace):
        self.close(force=kind is not None)


def replay(project: ProjectFiles, events: Iterable[ReplayEvent], profile: Profile, *, instrument=True) -> Iterator[Match]:
    worker = Worker(project, profile, instrument=instrument)
    try:
        for event in events:
            if isinstance(event, Reset):
                digest, ids = worker.project_digest, worker.ids
                worker.close()
                worker = None
                worker = Worker(project, profile, instrument=instrument)
                if (worker.project_digest, worker.ids) != (digest, ids):
                    raise ValueError("runtime export or reference mapping changed during replay")
                yield Match("reset", None, None, None)
            else:
                yield worker.request(event)
    finally:
        if worker is not None:
            worker.close()
