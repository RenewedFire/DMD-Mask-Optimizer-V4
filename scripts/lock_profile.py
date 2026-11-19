"""Verify the Twister fixture and the binaries selected for compatibility work."""

import argparse
import hashlib
import json
import re
import struct
import sys
import zipfile
from dataclasses import asdict, dataclass, replace
from pathlib import Path


PROFILE_PATH = Path(__file__).resolve().parents[1] / "profiles" / "twst_405.json"
PE_ARCHITECTURES = {0x014C: "x86", 0x8664: "x64", 0xAA64: "arm64"}
REQUIRED_COMPONENTS = ("ColorizingDMD editor", "bundled decoder", "PinMAME 3.6", "local Serum runtime")


class ProfileError(ValueError):
    """An input is missing or differs from the compatibility profile."""


@dataclass(frozen=True)
class RomMember:
    name: str
    size: int
    crc32: str
    sha256: str


@dataclass(frozen=True)
class Profile:
    rom_revision: str
    driver: str
    hardware: str
    width: int
    height: int
    native_shades: int
    delivery_semantics: str | None
    rom_sha256: str
    dump_sha256: str
    rom_members: tuple[RomMember, ...]
    components: dict[str, dict]
    profile_sha256: str
    authoring_binaries_verified: bool = False
    local_runtime_verified: bool = False
    native_binaries_verified: bool = False


def _check_sha256(path, expected, name):
    try:
        with path.open("rb") as contents:
            actual = hashlib.file_digest(contents, "sha256").hexdigest()
    except FileNotFoundError as exc:
        raise ProfileError(f"{name}: missing input {path}") from exc
    except OSError as exc:
        raise ProfileError(f"{name}: cannot read {path}: {exc}") from exc
    if actual != expected:
        raise ProfileError(f"{name}: SHA-256 mismatch for {path}; expected {expected}, got {actual}")
    return actual


def _rom_inventory(rom):
    members = []
    names = set()
    try:
        with zipfile.ZipFile(rom) as archive:
            for info in archive.infolist():
                if info.is_dir():
                    continue
                if info.filename.casefold() in names:
                    raise ProfileError(f"ROM member inventory: duplicate member {info.filename}")
                names.add(info.filename.casefold())
                with archive.open(info) as contents:
                    digest = hashlib.file_digest(contents, "sha256").hexdigest()
                members.append(RomMember(info.filename, info.file_size, f"{info.CRC:08x}", digest))
    except (OSError, zipfile.BadZipFile, NotImplementedError, RuntimeError) as exc:
        raise ProfileError(f"ROM member inventory: cannot read {rom}: {exc}") from exc
    return tuple(sorted(members, key=lambda member: member.name))


def _read_profile():
    try:
        record = json.loads(PROFILE_PATH.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise ProfileError(f"profile: cannot read {PROFILE_PATH}: {exc}") from exc
    _validate_profile(record)
    canonical = json.dumps(record, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return record, hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _field(record, field, valid, expected, name):
    if field not in record:
        raise ProfileError(f"{name}: missing {field}")
    value = record[field]
    if not valid(value):
        raise ProfileError(f"{name}: invalid {field}; expected {expected}")
    return value


def _nonempty_string(value):
    return isinstance(value, str) and bool(value.strip())


def _string_list(value):
    return isinstance(value, list) and all(_nonempty_string(item) for item in value)


def _hex(value, length):
    return isinstance(value, str) and re.fullmatch(rf"[0-9a-f]{{{length}}}", value) is not None


def _toolchain_path(value):
    return (
        _nonempty_string(value)
        and not any(character in value for character in '\\:<>"|?*\0')
        and all(part not in {"", ".", ".."} and part == part.rstrip(" .") for part in value.split("/"))
    )


def _windows_absolute_path(value):
    return isinstance(value, str) and re.fullmatch(r"[A-Za-z]:\\[^<>\"|?*\0]*", value) is not None


def _local_installation(record):
    provenance = record.get("provenance")
    return isinstance(provenance, dict) and provenance.get("kind") == "local-installation"


def _validate_provenance(record, name):
    provenance = record.get("provenance")
    if provenance is None:
        return False
    if not isinstance(provenance, dict):
        raise ProfileError(f"{name}: invalid provenance; expected an object")
    kind = _field(provenance, "kind", _nonempty_string, "a nonempty string", f"{name} provenance")
    if kind == "local-installation":
        _field(provenance, "installation_path", _windows_absolute_path,
               "an absolute Windows path", f"{name} provenance")
        return True
    if kind == "source-tree":
        _field(provenance, "source_tree_binary_git_blob", lambda value: _hex(value, 40),
               "a full lowercase Git blob ID", f"{name} provenance")
        return False
    raise ProfileError(f"{name}: invalid provenance kind {kind!r}; expected 'local-installation' or 'source-tree'")


def _validate_component(name, record):
    if not isinstance(record, dict):
        raise ProfileError(f"{name}: invalid component record; expected an object")
    _field(record, "binary", _toolchain_path, "a relative toolchain path", name)
    _field(record, "sha256", lambda value: _hex(value, 64), "a lowercase SHA-256 digest", name)
    _field(record, "architecture", lambda value: isinstance(value, str) and value in PE_ARCHITECTURES.values(),
           "x86, x64 or arm64", name)
    _field(record, "verification_scope", lambda value: value in {"authoring", "local-runtime"},
           "'authoring' or 'local-runtime'", name)
    if "file_version" in record:
        _field(record, "file_version", lambda value: isinstance(value, str) and re.fullmatch(r"\d+\.\d+\.\d+\.\d+", value) is not None,
               "a numeric a.b.c.d file version", name)
    _field(record, "source_commit", lambda value: _hex(value, 40), "a full lowercase Git commit ID", name)
    for field in ("source_repository", "release_tag", "release_url", "release_archive"):
        _field(record, field, _nonempty_string, "a nonempty string", name)

    local_installation = _validate_provenance(record, name)
    pending = _field(record, "pending", _string_list, "a list of nonempty strings", name)
    for field in ("compiler", "build_command"):
        _field(record, field, lambda value: _nonempty_string(value) or (bool(pending) and value is None),
               "a nonempty string or null while provenance is pending", name)
    _field(record, "compiler_flags", lambda value: (_string_list(value) and bool(value))
           or (bool(pending) and value is None), "a nonempty list of compiler flags or null while provenance is pending", name)
    _field(record, "release_archive_sha256",
           lambda value: _hex(value, 64) or (value is None and (bool(pending) or local_installation or record.get("provenance", {}).get("kind") == "source-tree")),
           "a lowercase SHA-256 digest or null while provenance is pending or locally installed", name)

    dependencies = _field(record, "dependencies", lambda value: isinstance(value, dict), "an object", name)
    if name in {"ColorizingDMD editor", "PinMAME 3.6"} and not dependencies:
        raise ProfileError(f"{name}: missing dependencies; expected a nonempty runtime dependency lock")
    for path, lock in dependencies.items():
        if not _toolchain_path(path):
            raise ProfileError(f"{name}: invalid dependencies path {path!r}; expected a relative toolchain path")
        digest = lock if isinstance(lock, str) else lock.get("sha256") if isinstance(lock, dict) else None
        if not _hex(digest, 64):
            raise ProfileError(f"{name}: invalid dependencies hash for {path}; expected a lowercase SHA-256 digest")
        if isinstance(lock, dict):
            _field(lock, "architecture", lambda value: value in PE_ARCHITECTURES.values(),
                   "x86, x64 or arm64", f"{name} dependency {path}")
            _field(lock, "file_version", lambda value: isinstance(value, str) and re.fullmatch(r"\d+\.\d+\.\d+\.\d+", value) is not None,
                   "a numeric a.b.c.d file version", f"{name} dependency {path}")


def _validate_profile(record):
    name = "profile"
    if not isinstance(record, dict):
        raise ProfileError("profile: expected an object")
    _field(record, "schema_version", lambda value: type(value) is int and value == 2, "version 2", name)
    _field(record, "lock_scopes", lambda value: isinstance(value, dict), "an object", name)
    for field in ("rom_revision", "driver", "hardware"):
        _field(record, field, _nonempty_string, "a nonempty string", name)
    for field in ("width", "height", "native_shades"):
        _field(record, field, lambda value: type(value) is int and value > 0, "a positive integer", name)
    _field(record, "delivery_semantics", lambda value: value is None or _nonempty_string(value),
           "a nonempty string or null", name)
    for field in ("rom_sha256", "dump_sha256"):
        _field(record, field, lambda value: _hex(value, 64), "a lowercase SHA-256 digest", name)
    _field(record, "rom_members", lambda value: isinstance(value, list) and bool(value),
           "a nonempty list of ROM members", name)

    components = _field(record, "components", lambda value: isinstance(value, dict), "an object", name)
    for component in REQUIRED_COMPONENTS:
        if component not in components:
            raise ProfileError(f"{component}: missing required component")
    for component, fields in components.items():
        _validate_component(component, fields)

    name = "bundled decoder"
    decoder = components[name]
    editor = components["ColorizingDMD editor"]
    for field in ("source_repository", "source_commit"):
        if decoder[field] != editor[field]:
            raise ProfileError(f"{name}: {field} differs from ColorizingDMD editor")
    source_version = _field(decoder, "source_version", _nonempty_string, "a nonempty string", name)
    source_tree_version = _field(decoder, "source_tree_binary_version", _nonempty_string, "a nonempty string", name)
    if decoder.get("provenance", {}).get("kind") == "source-tree" and source_version != source_tree_version:
        raise ProfileError(f"{name}: source_version {source_version} differs from source_tree_binary_version {source_tree_version}")


def _manifest_members(records):
    expected = {}
    seen = set()
    for record in records:
        name = "ROM member inventory"
        if not isinstance(record, dict):
            raise ProfileError(f"{name}: invalid member record; expected an object")
        member_name = _field(record, "name", _nonempty_string, "a nonempty string", name)
        name = f"{name} for {member_name!r}"
        if member_name.casefold() in seen:
            raise ProfileError(f"{name}: duplicate manifest member")
        seen.add(member_name.casefold())
        _field(record, "size", lambda value: type(value) is int and value >= 0, "a nonnegative integer", name)
        _field(record, "crc32", lambda value: _hex(value, 8), "a lowercase CRC-32 digest", name)
        _field(record, "sha256", lambda value: _hex(value, 64), "a lowercase SHA-256 digest", name)
        expected[member_name] = record
    return expected


def _verify_inventory(members, expected):
    actual = {member.name: asdict(member) for member in members}
    differences = []
    for name in sorted(expected.keys() - actual.keys()):
        differences.append(f"expected ROM member {name!r} missing from the archive")
    for name in sorted(actual.keys() - expected.keys()):
        differences.append(f"unexpected ROM member {name!r} in the archive")
    for name in sorted(expected.keys() & actual.keys()):
        for field in ("size", "crc32", "sha256"):
            if expected[name][field] != actual[name][field]:
                differences.append(f"{name!r} {field}: expected {expected[name][field]}, got {actual[name][field]}")
    if differences:
        raise ProfileError("ROM member inventory: " + "\n".join(differences))


def inspect_fixtures(rom: Path, dump: Path) -> Profile:
    """Verify only the supplied fixture bytes and return the selected profile metadata."""
    record, digest = _read_profile()
    expected_members = _manifest_members(record["rom_members"])
    rom_sha256 = _check_sha256(rom, record["rom_sha256"], "ROM")
    dump_sha256 = _check_sha256(dump, record["dump_sha256"], "dump")
    members = _rom_inventory(rom)
    _verify_inventory(members, expected_members)
    return Profile(
        rom_revision=record["rom_revision"], driver=record["driver"], hardware=record["hardware"],
        width=record["width"],
        height=record["height"], native_shades=record["native_shades"],
        delivery_semantics=record["delivery_semantics"], rom_sha256=rom_sha256,
        dump_sha256=dump_sha256, rom_members=members, components=record["components"],
        profile_sha256=digest,
    )


def _architecture(path, name):
    try:
        with path.open("rb") as binary:
            dos = binary.read(64)
            if len(dos) == 64 and dos[:2] == b"MZ":
                binary.seek(struct.unpack_from("<I", dos, 60)[0])
                header = binary.read(24)
                if len(header) == 24 and header[:4] == b"PE\0\0":
                    machine = struct.unpack_from("<H", header, 4)[0]
                    return PE_ARCHITECTURES.get(machine, f"unknown machine 0x{machine:04x}")
    except OSError as exc:
        raise ProfileError(f"{name}: cannot read PE architecture from {path}: {exc}") from exc
    raise ProfileError(f"{name}: invalid Windows PE header in {path}")


def _file_version(path, name):
    """Read the Windows VERSIONINFO FileVersion without third-party packages."""
    if sys.platform != "win32":
        raise ProfileError(f"{name}: Windows file-version verification requires Windows")
    import ctypes
    size = ctypes.windll.version.GetFileVersionInfoSizeW(str(path), None)
    if not size:
        raise ProfileError(f"{name}: missing Windows VERSIONINFO in {path}")
    data = ctypes.create_string_buffer(size)
    if not ctypes.windll.version.GetFileVersionInfoW(str(path), 0, size, data):
        raise ProfileError(f"{name}: cannot read Windows VERSIONINFO from {path}")
    value, length = ctypes.c_void_p(), ctypes.c_uint()
    if not ctypes.windll.version.VerQueryValueW(data, "\\\\", ctypes.byref(value), ctypes.byref(length)):
        raise ProfileError(f"{name}: invalid Windows VERSIONINFO in {path}")
    info = ctypes.cast(value, ctypes.POINTER(ctypes.c_uint32 * 13)).contents
    ms, ls = info[2], info[3]
    return f"{ms >> 16}.{ms & 0xffff}.{ls >> 16}.{ls & 0xffff}"


def _verify_binary(path, lock, name):
    _check_sha256(path, lock["sha256"], name)
    architecture = _architecture(path, name)
    if architecture != lock["architecture"]:
        raise ProfileError(f"{name}: architecture mismatch for {path}; expected {lock['architecture']}, got {architecture}")
    if "file_version" in lock:
        version = _file_version(path, name)
        if version != lock["file_version"]:
            raise ProfileError(f"{name}: file-version mismatch for {path}; expected {lock['file_version']}, got {version}")


def _verify_component(name, component, toolchain):
    _verify_binary(toolchain / component["binary"], component, name)
    for relative_path, lock in component["dependencies"].items():
        dependency = lock if isinstance(lock, dict) else {"sha256": lock}
        _verify_binary(toolchain / relative_path, dependency, f"{name} dependency {relative_path}")
    if component["pending"]:
        raise ProfileError(f"{name}: missing provenance: {', '.join(component['pending'])}")


def lock_profile(rom: Path, dump: Path, toolchain: Path, scope="local-runtime") -> Profile:
    """Verify one explicit lock scope without treating local runtime as editor parity."""
    if scope not in {"authoring", "local-runtime"}:
        raise ProfileError(f"unknown lock scope {scope!r}")
    profile = inspect_fixtures(rom, dump)
    scope_errors = {"authoring": [], "local-runtime": []}
    for name, component in profile.components.items():
        try:
            _verify_component(name, component, toolchain)
        except ProfileError as exc:
            scope_errors[component["verification_scope"]].append(str(exc))
    if scope_errors[scope]:
        raise ProfileError("\n".join(scope_errors[scope]))
    # The unselected scope is deliberately *unverified*, even if its files happen
    # to be present: callers must make a separate explicit assertion.
    authoring_verified = scope == "authoring"
    local_runtime_verified = scope == "local-runtime"
    return replace(profile, authoring_binaries_verified=authoring_verified,
                   local_runtime_verified=local_runtime_verified,
                   native_binaries_verified=False)

def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rom", required=True, type=Path)
    parser.add_argument("--dump", required=True, type=Path)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--toolchain", type=Path, help="directory containing the locked Windows binaries")
    mode.add_argument("--fixtures-only", action="store_true", help="check the ROM and dump without native binaries")
    parser.add_argument("--scope", choices=("authoring", "local-runtime"), default="local-runtime",
                        help="native lock scope; local runtime does not assert editor parity")
    args = parser.parse_args(argv)
    try:
        if args.fixtures_only:
            profile = inspect_fixtures(args.rom, args.dump)
        else:
            profile = lock_profile(args.rom, args.dump, args.toolchain, args.scope)
    except ProfileError as exc:
        print(exc, file=sys.stderr)
        return 1
    print(json.dumps(asdict(profile), indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
