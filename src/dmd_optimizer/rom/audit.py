"""Content-addressed ROM archive audits independent of archive filenames."""

from __future__ import annotations

import hashlib
import zipfile
from dataclasses import dataclass
from pathlib import Path


class RomAuditError(ValueError):
    """A selected archive cannot be bound to the locked ROM profile."""


@dataclass(frozen=True)
class AuditMember:
    name: str
    size: int
    crc32: str
    sha256: str


@dataclass(frozen=True)
class AuditResult:
    rom_path: Path
    archive_sha256: str
    content_sha256: str
    profile_sha256: str
    revision: str
    driver: str
    members: tuple[AuditMember, ...]
    dependencies: tuple[str, ...] = ()
    native_audit_digest: str | None = None


def _digest_file(path: Path) -> str:
    with path.open("rb") as source:
        return hashlib.file_digest(source, "sha256").hexdigest()


def _expected(profile) -> dict[str, object]:
    result: dict[str, object] = {}
    for item in profile.rom_members:
        name = item["name"] if isinstance(item, dict) else item.name
        key = name.casefold()
        if key in result:
            raise RomAuditError(f"profile contains duplicate ROM member {name!r}")
        result[key] = item
    return result


def _value(item: object, name: str):
    return item[name] if isinstance(item, dict) else getattr(item, name)


def _safe(name: str) -> bool:
    path = Path(name.replace("\\", "/"))
    return bool(name) and not path.is_absolute() and ".." not in path.parts and len(path.parts) == 1


def audit_rom(path: Path, profile) -> AuditResult:
    """Validate selected archive members against a locked profile, by content."""
    path = Path(path)
    expected = _expected(profile)
    actual: list[AuditMember] = []
    names: set[str] = set()
    try:
        with zipfile.ZipFile(path) as archive:
            for info in archive.infolist():
                if info.is_dir():
                    continue
                if not _safe(info.filename):
                    raise RomAuditError(f"unsafe ROM member name {info.filename!r}")
                key = info.filename.casefold()
                if key in names:
                    raise RomAuditError(f"duplicate ROM member {info.filename!r}")
                names.add(key)
                with archive.open(info) as source:
                    digest = hashlib.file_digest(source, "sha256").hexdigest()
                actual.append(AuditMember(info.filename, info.file_size, f"{info.CRC:08x}", digest))
    except RomAuditError:
        raise
    except (OSError, zipfile.BadZipFile, RuntimeError, NotImplementedError) as error:
        raise RomAuditError(f"cannot read ROM archive {path}: {error}") from error

    by_name = {member.name.casefold(): member for member in actual}
    missing = sorted(set(expected) - set(by_name))
    extra = sorted(set(by_name) - set(expected))
    if missing:
        raise RomAuditError(f"missing locked ROM member(s): {', '.join(missing)}")
    if extra:
        raise RomAuditError(f"unexpected ROM member(s): {', '.join(extra)}")
    for key, lock in expected.items():
        member = by_name[key]
        for field in ("size", "crc32", "sha256"):
            wanted = _value(lock, field)
            if getattr(member, field) != wanted:
                raise RomAuditError(f"ROM member {member.name!r} {field.upper()} differs from locked profile")

    ordered = tuple(sorted(actual, key=lambda member: member.name.casefold()))
    content = hashlib.sha256()
    for member in ordered:
        content.update(f"{member.name}\0{member.size}\0{member.crc32}\0{member.sha256}\n".encode("utf-8"))
    profile_digest = getattr(profile, "profile_sha256", "")
    return AuditResult(path, _digest_file(path), content.hexdigest(), profile_digest,
                       profile.rom_revision, profile.driver, ordered)
