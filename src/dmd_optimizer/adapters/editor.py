"""Build verified requests for the original ColorizingDMD editor bridge."""

import hashlib
import json
import os
import shutil
import subprocess
import tempfile
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

from scripts.lock_profile import Profile, ProfileError, _toolchain_path, _verify_binary


_DECODER_SHA256 = "da71fa73e838ab3e257a2a73c8f74d88a3336615930761fa494a251822e0c2d5"
_EDITOR = "ColorizingDMD editor"
_DECODER = "bundled decoder"


class EditorBridgeError(RuntimeError):
    """The editor inputs, staging, or bridge operation could not be verified."""

    def __init__(self, message: str, *, diagnostics: Mapping[str, object] | None = None):
        super().__init__(message)
        self.diagnostics = dict(diagnostics or {})


@dataclass(frozen=True)
class Reference:
    id: str
    native_pixels: bytes
    ignore_bitmap: bytes | None
    shape: bool = False


@dataclass(frozen=True)
class ProjectFiles:
    root: Path
    manifest_path: Path
    runtime_export: Path | None
    observations: Mapping[str, object]


def _editor_files(profile: Profile):
    """Translate the profile's toolchain paths to paths relative to the editor."""
    editor = profile.components[_EDITOR]
    decoder = profile.components[_DECODER]
    if decoder["sha256"] != _DECODER_SHA256:
        raise EditorBridgeError(f"{_DECODER}: profile must pin source-tree Serum 2.1.0 ({_DECODER_SHA256})")

    toolchain_editor = Path(editor["binary"]).parent
    records = [(editor["binary"], editor, _EDITOR)]
    for path, lock in editor["dependencies"].items():
        records.append((path, lock if isinstance(lock, dict) else {"sha256": lock},
                        f"{_EDITOR} dependency {path}"))
    # The pinned DLL reports its 2.1.0 identity via Serum_GetVersion and has
    # no Windows VERSIONINFO resource. Its exact digest identifies those bytes.
    decoder_lock = {"sha256": _DECODER_SHA256, "architecture": "x64"}
    records.append((decoder["binary"], decoder_lock, _DECODER))

    files = []
    names = set()
    for path, lock, name in records:
        if not _toolchain_path(path) or not Path(path).is_relative_to(toolchain_editor):
            raise EditorBridgeError(f"{name}: invalid editor profile path {path!r}")
        relative = Path(path).relative_to(toolchain_editor)
        key = relative.as_posix().casefold()
        if key in names:
            raise EditorBridgeError(f"{name}: duplicate editor file {relative}")
        names.add(key)
        files.append((relative, lock, name))
    return files


def _overlaps(first: Path, second: Path) -> bool:
    return first.is_relative_to(second) or second.is_relative_to(first)


def _installation(profile: Profile) -> Path:
    return Path(profile.components[_EDITOR]["provenance"]["installation_path"]).resolve()


def _verify_staged_file(path: Path, lock: dict, name: str) -> None:
    try:
        if path.resolve() != path:
            raise EditorBridgeError(f"{name}: staged file is redirected: {path}")
        _verify_binary(path, lock, name)
    except ProfileError as exc:
        raise EditorBridgeError(str(exc)) from exc
    except OSError as exc:
        raise EditorBridgeError(f"{name}: cannot verify {path}: {exc}") from exc


def stage_editor(
    source_root: Path, destination: Path, profile: Profile, *, decoder_path: Path | None = None,
) -> Path:
    """Copy the locked editor to a new directory and verify the copied binaries.

    Supply decoder_path for an installed editor. With a preassembled source tree,
    the adjacent DLL must already match the source-tree Serum lock.
    """
    source = source_root.resolve()
    target = destination.resolve()
    if _overlaps(source, target) or _overlaps(_installation(profile), target):
        raise EditorBridgeError("staging destination must be outside the editor source and installation")
    if target.exists():
        raise EditorBridgeError(f"staging destination already exists: {target}")
    if not source.is_dir():
        raise EditorBridgeError(f"editor source root is missing: {source}")
    files = _editor_files(profile)

    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix=".editor-stage-", dir=target.parent) as work:
            staging = Path(work) / "editor"
            staging.mkdir()
            for relative, lock, name in files:
                origin = decoder_path if name == _DECODER and decoder_path is not None else source / relative
                copied = staging / relative
                try:
                    copied.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copyfile(origin, copied)
                except OSError as exc:
                    raise EditorBridgeError(f"{name}: cannot copy {origin}: {exc}") from exc
                _verify_staged_file(copied, lock, name)
            staging.rename(target)
    except OSError as exc:
        raise EditorBridgeError(f"cannot stage editor at {target}: {exc}") from exc
    return target


def _encode_references(refs: Sequence[Reference], profile: Profile) -> list[dict]:
    size = profile.width * profile.height
    ids = set()
    encoded = []
    for ref in refs:
        if not isinstance(ref.id, str) or not ref.id.strip():
            raise EditorBridgeError("reference ID must be a nonempty string")
        if ref.id in ids:
            raise EditorBridgeError(f"duplicate reference ID {ref.id!r}")
        ids.add(ref.id)
        pixels = ref.native_pixels
        if not isinstance(pixels, bytes) or len(pixels) != size:
            raise EditorBridgeError(f"reference {ref.id!r} must contain {size} native pixels as bytes")
        if max(pixels, default=0) >= profile.native_shades:
            raise EditorBridgeError(f"reference {ref.id!r} contains out-of-range native shades")

        mask = ref.ignore_bitmap
        if mask is not None:
            if not isinstance(mask, bytes) or len(mask) != size:
                raise EditorBridgeError(f"reference {ref.id!r} must contain {size} mask pixels as bytes")
            if max(mask, default=0) > 1:
                raise EditorBridgeError(f"reference {ref.id!r} must have a binary ignore bitmap")
        if ref.shape is not False:
            raise EditorBridgeError(f"reference {ref.id!r} must use shape=false")

        encoded.append({
            "id": ref.id,
            "native_pixels": list(pixels),
            "source_sha256": hashlib.sha256(pixels).hexdigest(),
            "ignore_bitmap": None if mask is None else list(mask),
            "ignore_sha256": None if mask is None else hashlib.sha256(mask).hexdigest(),
            "shape": False,
        })
    if not encoded:
        raise EditorBridgeError("at least one reference is required")
    return encoded


def serialize_request(
    folder: Path,
    refs: Sequence[Reference],
    profile: Profile,
    *,
    editor_root: Path | None = None,
    config_root: Path | None = None,
    deadline_ms: int = 60_000,
) -> str:
    """Validate generated references and a staged editor, then encode a v1 request."""
    references = _encode_references(refs, profile)
    if editor_root is None or not editor_root.is_dir():
        raise EditorBridgeError(f"staged editor root is missing: {editor_root}")
    if type(deadline_ms) is not int or deadline_ms <= 0:
        raise EditorBridgeError("deadline_ms must be a positive integer")

    editor = editor_root.resolve()
    project = folder.resolve()
    config = (
        config_root.resolve()
        if config_root is not None
        else (project.parent / f"{project.name}-editor-config").resolve()
    )
    installation = _installation(profile)
    if _overlaps(editor, installation):
        raise EditorBridgeError("staged editor root must be outside the editor installation")
    if any(_overlaps(output, protected) for output in (project, config) for protected in (editor, installation)):
        raise EditorBridgeError("project and config roots must be outside the staged editor and editor installation")
    if _overlaps(project, config):
        raise EditorBridgeError("project and config roots must be separate")

    for relative, lock, name in _editor_files(profile):
        _verify_staged_file(editor / relative, lock, name)
    return json.dumps({
        "schema_version": 1,
        "editor_root": str(editor),
        "expected_decoder_sha256": _DECODER_SHA256,
        "project_root": str(project),
        "config_root": str(config),
        "deadline_ms": deadline_ms,
        "width": profile.width,
        "height": profile.height,
        "native_shades": profile.native_shades,
        "references": references,
    })


def write_project(
    folder: Path, refs: Sequence[Reference], profile: Profile, *, editor_root: Path | None = None,
    deadline_ms: int = 60_000,
) -> ProjectFiles:
    """Run the original-editor preflight and retain its diagnostics in a fresh config root."""
    request = serialize_request(folder, refs, profile, editor_root=editor_root, deadline_ms=deadline_ms)
    default_bridge = Path(__file__).resolve().parents[3] / "build" / "editor_bridge.exe"
    bridge = Path(os.environ.get("DMD_EDITOR_BRIDGE_PATH", default_bridge)).resolve()
    if not bridge.is_file():
        raise EditorBridgeError(f"editor_bridge.exe is unavailable at {bridge}")

    config = Path(json.loads(request)["config_root"])
    try:
        config.mkdir(parents=True, exist_ok=False)
        try:
            result = subprocess.run(
                [str(bridge)], input=request.encode("utf-8"), capture_output=True,
                cwd=config, timeout=deadline_ms / 1000, check=False,
            )
        except subprocess.TimeoutExpired as exc:
            (config / "bridge.stdout").write_bytes(exc.stdout or b"")
            (config / "bridge.stderr").write_bytes(exc.stderr or b"")
            raise EditorBridgeError(f"editor bridge timed out after {deadline_ms} ms; see {config}") from exc
        (config / "bridge.stdout").write_bytes(result.stdout)
        (config / "bridge.stderr").write_bytes(result.stderr)
    except OSError as exc:
        raise EditorBridgeError(f"cannot run editor bridge with fresh config {config}: {exc}") from exc

    try:
        response = json.loads(result.stdout.decode("utf-8"))
    except (UnicodeError, ValueError) as exc:
        raise EditorBridgeError(
            f"editor bridge exit code {result.returncode}, invalid JSON response; see {config}"
        ) from exc
    if (not isinstance(response, dict) or type(response.get("schema_version")) is not int
            or response["schema_version"] != 1):
        raise EditorBridgeError(f"invalid editor bridge schema version; see {config}")
    if response.get("status") == "error":
        diagnostics = response.get("diagnostics")
        raise EditorBridgeError(
            f"editor bridge {response.get('stage')} (exit code {result.returncode}): "
            f"{response.get('message')}; see {config}",
            diagnostics=diagnostics if isinstance(diagnostics, dict) else None,
        )
    if result.returncode:
        raise EditorBridgeError(f"editor bridge exit code {result.returncode}; see {config}")
    # The capability probe cannot attest to a save, reopen, or export.
    raise EditorBridgeError(f"no verified original-editor round-trip manifest; see {config}")
