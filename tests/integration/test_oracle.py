import hashlib
import json
import os
import struct
import zlib
import zipfile
from pathlib import Path

import pytest

from dmd_optimizer.adapters.editor import ProjectFiles
from scripts.lock_profile import Profile, RomMember, _read_profile

ROOT = Path(__file__).resolve().parents[2]
GOLD = ROOT / "tests/fixtures/editor_roundtrip/golden"
SOURCES = (GOLD / "twst_405.cRP").read_bytes()[64:64 + 3 * 4096]
A, B, C = (SOURCES[i:i + 4096] for i in range(0, len(SOURCES), 4096))
COLLISION_BITS = (0, 6, 9, 10, 16, 20, 21, 22, 24, 25, 27, 28, 30, 31, 32)


def flip(frame, positions):
    result = bytearray(frame)
    for i in positions:
        result[i] ^= 1
    return bytes(result)


@pytest.fixture(scope="module")
def case(tmp_path_factory):
    from dmd_optimizer.verify import oracle
    record, digest = _read_profile()
    del record["schema_version"], record["lock_scopes"]
    record["rom_members"] = tuple(RomMember(**m) for m in record["rom_members"])
    return oracle, variant(tmp_path_factory.mktemp("native") / "diagnostic", "original", "ABC"), Profile(**record, profile_sha256=digest)


def test_unmodified_editor_export_is_incompatible(case):
    api, _, profile = case
    golden = ProjectFiles(GOLD, GOLD / "references.json", GOLD / "twst_405.cRZ", {})
    with pytest.raises(api.IncompatibleExport, match="byte 102"):
        list(api.replay(golden, [api.Frame(A)], profile))


requires_decoder = pytest.mark.skipif(
    not os.environ.get("DMD_EDITOR_DECODER_PATH"),
    reason="set DMD_EDITOR_DECODER_PATH and build the x64 serum_worker for native qualification",
)


@requires_decoder
def test_diagnostic_sequence_and_public_output_parity(case):
    api, project, profile = case
    frames = [A, flip(A, [4]), flip(A, [7]), B, B, C, C, flip(C, [4]), C]
    events = [api.Frame(p) for p in frames] + [api.Reset(), api.Frame(bytes(4096)), api.Frame(C), api.AdvanceTime(1)]
    observed = list(api.replay(project, events, profile))
    production = list(api.replay(project, events, profile, instrument=False))
    assert [m.reference for m in observed if m.event == "frame"] == ["A", "A", None, "B", "B", "C", "C", None, "C", None, "C"]
    assert [m.output for m in observed] == [m.output for m in production]
    assert [observed[i].reference_origin for i in [5, 6, 7, 8]] == ["frameID", "unchanged-crc", None, "unchanged-crc"]
    assert observed[6].output.result == observed[7].output.result == 0xffffffff
    assert observed[-1].event == "advance-time" and observed[-1].output.result == 0
    assert len({observed[i].output.pixels_sha256 for i in [0, 3, 5]}) == 3


@requires_decoder
def test_compared_bytes_and_real_crc_collision(case):
    api, project, profile = case
    ignored = bytearray(4096)
    ignored[4] = 1
    compared = api.compared_bytes
    assert compared(A, ignored) == compared(flip(A, [4]), ignored) == A[:4] + A[5:]
    collision = flip(C, COLLISION_BITS)
    assert compared(C, None) != compared(collision, None)
    assert [zlib.crc32(compared(frame, mask)) for frame, mask in [(A, ignored), (B, ignored), (C, None), (collision, None)]] == [0xb52ee996, 0xde0c37ff, 0xf57d4265, 0xf57d4265]
    assert [m.reference for m in api.replay(project, [api.Frame(collision)], profile)] == ["C"]


def variant(folder, mode, names):
    """Controlled matcher experiment based on the three-reference v2 editor output."""
    folder.mkdir()
    crom = bytearray((GOLD / "twst_405.cROM").read_bytes())
    assert hashlib.sha256(crom).hexdigest() == "d020f1e55a9b1d356c039b8035d42456eaf22c3cfcb576849cf8a864f38e996a"
    if mode == "hidden":
        crom[124:4220] = bytes([1]) * 4096
        hashes = [0, 0, zlib.crc32(C)]
    elif mode == "original":
        hashes = [0xb52ee996, 0xde0c37ff, 0xf57d4265]
    else:
        # A's mask also accepts exact C. B keeps its own hash and starts its
        # search in the same mask group as A, including after ordinal wrap.
        hashes = [zlib.crc32(C[:4] + C[5:]), 0xde0c37ff, zlib.crc32(C)]
    old_slots = [0, 0, 255]
    colors = [crom[4223+i*8192:4223+(i+1)*8192] for i in range(3)]
    for ordinal, name in enumerate(names):
        old = "ABC".index(name)
        struct.pack_into("<I", crom, 106 + 4*ordinal, hashes[old])
        crom[121+ordinal] = old_slots[old]
        crom[4223+ordinal*8192:4223+(ordinal+1)*8192] = colors[old]
    export = folder / "twst_405.cRZ"
    with zipfile.ZipFile(export, "w", zipfile.ZIP_DEFLATED) as package:
        # Match the decoder's 102-byte header in this synthetic diagnostic copy only.
        package.writestr(zipfile.ZipInfo("twst_405.cRom"), crom[:102] + crom[106:], compress_type=zipfile.ZIP_DEFLATED)
    manifest = {"references": [{"id": n, "ordinal": i} for i, n in enumerate(names)],
                "runtime_export": export.name, "files": [{"path": export.name, "sha256": hashlib.sha256(export.read_bytes()).hexdigest()}]}
    sidecar = folder / "references.json"
    sidecar.write_text(json.dumps(manifest))
    return ProjectFiles(folder, sidecar, export, {})


@pytest.mark.parametrize("mode,names,frames,expected", [
    ("hidden", "ABC", [bytes(4096), C, B], ["A", "A", "A"]),
    ("ambiguous", "CAB", [C, B, C, None, C], ["C", "B", "A", "C"]),
    ("ambiguous", "ACB", [C, B, C, None, C], ["A", "B", "A", "A"]),
])
@requires_decoder
def test_group_lookup_and_reference_order(case, tmp_path, mode, names, frames, expected):
    api, _, profile = case
    project = variant(tmp_path / "variant", mode, names)
    events = [api.Reset() if p is None else api.Frame(p) for p in frames]
    instr = list(api.replay(project, events, profile))
    prod = list(api.replay(project, events, profile, instrument=False))
    assert [m.reference for m in instr if m.event == "frame"] == expected
    assert [m.output for m in instr] == [m.output for m in prod]
    for match in instr:
        if match.event == "frame":
            frame = dict(A=A, B=B, C=C)[match.reference]
            rgb = b"".join(struct.pack("<H", [0, 0x5140, 0xa280, 0xfbe0][shade]) for shade in frame)
            assert match.output.pixels_sha256 == hashlib.sha256(rgb).hexdigest()


@requires_decoder
def test_worker_rejects_invalid_header_before_reading_payload(case):
    api, project, profile = case
    for bad in [b"DMDW\x02\x01\x00\x10", b"DMDW\x01\x01\x01\x10", b"DMDW\x01\x09\x00\x00"]:
        with api.Worker(project, profile) as worker:
            worker.process.stdin.write(bad)
            worker.process.stdin.flush()
            assert worker.process.wait(timeout=3) != 0


@requires_decoder
def test_timeout_only_terminates_affected_worker(case):
    api, project, profile = case
    with api.Worker(project, profile) as survivor, api.Worker(project, profile) as stalled:
        with pytest.raises(TimeoutError):
            stalled.request(api.AdvanceTime(1000), timeout=0.05)
        assert stalled.process.poll() is not None
        assert survivor.request(api.Frame(B)).reference == "B"
    assert survivor.process.returncode == 0


@requires_decoder
def test_rejects_bad_geometry_shades_and_decoder_lock(case, tmp_path, monkeypatch):
    api, project, profile = case
    with api.Worker(project, profile) as worker:
        for pixels in [b"\x00", b"\x04" * 4096]:
            with pytest.raises(ValueError):
                worker.request(api.Frame(pixels))
        assert worker.request(api.Frame(A)).reference == "A"
    bad = tmp_path / "serum64.dll"
    bad.write_bytes(b"wrong decoder")
    monkeypatch.setenv("DMD_EDITOR_DECODER_PATH", str(bad))
    with pytest.raises(ValueError, match="SHA-256"):
        list(api.replay(project, [api.Frame(A)], profile))
