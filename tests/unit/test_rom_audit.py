from __future__ import annotations

import hashlib
import zipfile
from pathlib import Path
from types import SimpleNamespace

import pytest


def _member(name: str, payload: bytes):
    return {"name": name, "size": len(payload), "crc32": f"{zipfile.crc32(payload):08x}", "sha256": hashlib.sha256(payload).hexdigest()}


def _profile():
    members = [_member("cpu.bin", b"cpu"), _member("dmd.bin", b"dmd"), _member("sound.bin", b"snd")]
    return SimpleNamespace(rom_sha256="0" * 64, profile_sha256="a" * 64, rom_revision="fixture", driver="fixture_driver", rom_members=members)


def _archive(path: Path, entries: list[tuple[str, bytes]]):
    with zipfile.ZipFile(path, "w") as output:
        for name, payload in entries:
            output.writestr(name, payload)


def test_audit_matches_member_content_when_archive_is_renamed(tmp_path):
    from dmd_optimizer.rom.audit import audit_rom

    profile = _profile()
    path = tmp_path / "unrelated-name.zip"
    _archive(path, [("cpu.bin", b"cpu"), ("dmd.bin", b"dmd"), ("sound.bin", b"snd")])
    result = audit_rom(path, profile)

    assert result.revision == "fixture"
    assert result.driver == "fixture_driver"
    assert result.rom_path == path
    assert [member.name for member in result.members] == ["cpu.bin", "dmd.bin", "sound.bin"]


@pytest.mark.parametrize("entries, message", [
    ([("cpu.bin", b"bad"), ("dmd.bin", b"dmd"), ("sound.bin", b"snd")], "CRC32"),
    ([("cpu.bin", b"cpu"), ("dmd.bin", b"dmd")], "missing"),
    ([("CPU.BIN", b"cpu"), ("cpu.bin", b"cpu"), ("dmd.bin", b"dmd"), ("sound.bin", b"snd")], "duplicate"),
])
def test_audit_rejects_bad_member_inventory(tmp_path, entries, message):
    from dmd_optimizer.rom.audit import RomAuditError, audit_rom

    path = tmp_path / "bad.zip"; _archive(path, entries)
    with pytest.raises(RomAuditError, match=message):
        audit_rom(path, _profile())


def test_audit_rejects_unsafe_member_name(tmp_path):
    from dmd_optimizer.rom.audit import RomAuditError, audit_rom

    path = tmp_path / "unsafe.zip"
    _archive(path, [("../cpu.bin", b"cpu"), ("dmd.bin", b"dmd"), ("sound.bin", b"snd")])
    with pytest.raises(RomAuditError, match="unsafe"):
        audit_rom(path, _profile())
