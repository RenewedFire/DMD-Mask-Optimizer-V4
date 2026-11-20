import hashlib
import json
import os
import struct
from dataclasses import replace
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator, ValidationError

from dmd_optimizer.adapters.editor import (
    EditorBridgeError,
    Reference,
    serialize_request,
    stage_editor,
    write_project,
)
from scripts.lock_profile import Profile, RomMember, _read_profile


PINNED_DECODER = "da71fa73e838ab3e257a2a73c8f74d88a3336615930761fa494a251822e0c2d5"


@pytest.fixture(scope="module")
def bridge_schema():
    path = Path(__file__).resolve().parents[2] / "schemas" / "editor-bridge-v1.json"
    schema = json.loads(path.read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    return Draft202012Validator(schema)


@pytest.fixture
def bridge_request(tmp_path):
    return {
        "schema_version": 1,
        "editor_root": str(tmp_path / "stage"),
        "expected_decoder_sha256": PINNED_DECODER,
        "project_root": str(tmp_path / "project"),
        "config_root": str(tmp_path / "config"),
        "deadline_ms": 1500,
        "width": 1,
        "height": 1,
        "native_shades": 4,
        "references": [{
            "id": "A",
            "native_pixels": [0],
            "source_sha256": hashlib.sha256(b"\x00").hexdigest(),
            "ignore_bitmap": [1],
            "ignore_sha256": hashlib.sha256(b"\x01").hexdigest(),
            "shape": False,
        }],
    }


def test_schema_accepts_masked_and_unmasked_requests(bridge_schema, bridge_request):
    masked = bridge_request["references"][0]
    bridge_request["references"].append({
        **masked, "id": "B", "ignore_bitmap": None, "ignore_sha256": None,
    })

    bridge_schema.validate(bridge_request)


@pytest.mark.parametrize("missing", ["ignore_bitmap", "ignore_sha256"])
def test_schema_rejects_unpaired_mask_fields(bridge_schema, bridge_request, missing):
    bridge_request["references"][0][missing] = None

    with pytest.raises(ValidationError):
        bridge_schema.validate(bridge_request)


def test_schema_accepts_success_and_error_responses(bridge_schema):
    digest = hashlib.sha256(b"\x00").hexdigest()
    bridge_schema.validate({
        "schema_version": 1,
        "status": "ok",
        "files": [{"path": "project.cRZ", "sha256": digest, "size": 1, "header": {}}],
        "references": [{
            "id": "A", "ordinal": 0, "native_pixels": [0], "source_sha256": digest,
            "ignore_sha256": None, "shape": False, "slot": 255,
        }],
        "custom_mask_count": 0,
        "unmasked_sentinel": 255,
        "sidecar_path": None,
        "runtime_export": None,
        "observations": {},
    })
    bridge_schema.validate({
        "schema_version": 1,
        "status": "error",
        "stage": "save",
        "message": "Project save failed",
        "diagnostics": {},
    })


@pytest.fixture
def profile():
    record, digest = _read_profile()
    del record["schema_version"], record["lock_scopes"]
    record["rom_members"] = tuple(RomMember(**member) for member in record["rom_members"])
    return Profile(**record, profile_sha256=digest)


@pytest.fixture
def case():
    pixels = bytes(range(4)) * 1024
    # Positions 4 and 5 differ for A/B. Position 4 is ignored.
    other_pixels = pixels[:4] + b"\x03\x02" + pixels[6:]
    mask = b"\x00" * 4 + b"\x01" + b"\x00" * 4091
    return (
        Reference("A", pixels, mask),
        Reference("B", other_pixels, mask),
        Reference("C", pixels[::-1], None),
    )


@pytest.mark.parametrize(
    ("change", "diagnostic"),
    [
        ({"native_pixels": bytes(4095)}, "4096 native pixels"),
        ({"native_pixels": bytes(4095) + b"\x04"}, "native shades"),
        ({"id": ""}, "nonempty"),
        ({"id": " \t"}, "nonempty"),
        ({"id": "B"}, "duplicate reference ID"),
        ({"ignore_bitmap": bytes(4095)}, "4096 mask pixels"),
        ({"ignore_bitmap": bytes(4095) + b"\x02"}, "binary ignore bitmap"),
        ({"shape": True}, "shape=false"),
    ],
)
def test_request_rejects_invalid_references_before_editor_check(
    case, profile, tmp_path, change, diagnostic,
):
    invalid_refs = (replace(case[0], **change), *case[1:])
    with pytest.raises(EditorBridgeError, match=diagnostic):
        write_project(tmp_path / "project", invalid_refs, profile, editor_root=tmp_path / "missing")


def test_write_project_requires_an_explicit_staged_editor(case, profile, tmp_path):
    project = tmp_path / "project"
    with pytest.raises(EditorBridgeError, match="staged editor root"):
        write_project(project, case, profile)
    with pytest.raises(EditorBridgeError, match="staged editor root.*missing"):
        write_project(project, case, profile, editor_root=tmp_path / "missing")
    assert not project.exists()


def test_stage_editor_rejects_output_inside_source(profile, tmp_path):
    source = tmp_path / "source"
    source.mkdir()

    with pytest.raises(EditorBridgeError, match="outside the editor source"):
        stage_editor(source, source / "stage", profile)

    assert list(source.iterdir()) == []


def test_stage_editor_preserves_existing_destination(profile, tmp_path):
    source = tmp_path / "source"
    source.mkdir()
    staged = tmp_path / "stage"
    staged.mkdir()
    marker = staged / "owned.txt"
    marker.write_bytes(b"existing files")

    with pytest.raises(EditorBridgeError, match="destination.*already exists"):
        stage_editor(source, staged, profile)

    assert marker.read_bytes() == b"existing files"


def test_stage_editor_rejects_malformed_executable(profile, tmp_path):
    source = tmp_path / "source"
    source.mkdir()
    exe = source / "ColorizingDMD.exe"
    exe.write_bytes(b"fake editor")
    staged = tmp_path / "stage"

    with pytest.raises(EditorBridgeError, match="ColorizingDMD editor.*SHA-256 mismatch"):
        stage_editor(source, staged, profile)

    assert not staged.exists()
    assert exe.read_bytes() == b"fake editor"
    assert sorted(path.name for path in tmp_path.iterdir()) == ["source"]


@pytest.fixture
def synthetic_editor(profile, tmp_path):
    root = tmp_path / "synthetic-editor"
    root.mkdir()
    dos = bytearray(64)
    dos[:2] = b"MZ"
    struct.pack_into("<I", dos, 60, 64)
    exe = bytes(dos) + b"PE\0\0" + struct.pack("<H", 0x8664) + bytes(18)
    (root / "ColorizingDMD.exe").write_bytes(exe)
    (root / "test.dll").write_bytes(b"generated dependency")
    profile.components["ColorizingDMD editor"].update(
        sha256=hashlib.sha256(exe).hexdigest(),
        dependencies={"editor/test.dll": hashlib.sha256(b"generated dependency").hexdigest()},
    )
    return root


def test_rejects_wrong_decoder_with_generated_editor(synthetic_editor, profile, tmp_path):
    (synthetic_editor / "serum64.dll").write_bytes(b"wrong decoder")
    staged = tmp_path / "stage"

    with pytest.raises(EditorBridgeError, match="bundled decoder.*SHA-256 mismatch"):
        stage_editor(synthetic_editor, staged, profile)

    assert not staged.exists()


def test_rejects_mismatched_dependency(synthetic_editor, profile, tmp_path):
    (synthetic_editor / "test.dll").write_bytes(b"changed dependency")
    staged = tmp_path / "stage"

    with pytest.raises(EditorBridgeError, match=r"test\.dll.*SHA-256 mismatch"):
        stage_editor(synthetic_editor, staged, profile)

    assert not staged.exists()


@pytest.mark.parametrize("which", ["project", "config"])
def test_request_rejects_paths_inside_staged_editor(case, profile, tmp_path, which):
    staged = tmp_path / "stage"
    staged.mkdir()
    project = staged / "project" if which == "project" else tmp_path / "project"
    config = staged / "config" if which == "config" else tmp_path / "config"

    with pytest.raises(EditorBridgeError, match="roots must be outside the staged editor"):
        serialize_request(project, case, profile, editor_root=staged, config_root=config)


@pytest.mark.parametrize(
    "relative_root", [".", "child", ".."], ids=["installation", "descendant", "ancestor"],
)
def test_request_rejects_editor_root_overlapping_installation(
    case, profile, tmp_path, relative_root,
):
    installation = tmp_path / "installed" / "ColorizingDMD"
    editor_root = (installation / relative_root).resolve()
    installation.mkdir(parents=True)
    editor_root.mkdir(parents=True, exist_ok=True)
    profile.components["ColorizingDMD editor"]["provenance"]["installation_path"] = str(installation)

    with pytest.raises(EditorBridgeError, match="staged editor root.*editor installation"):
        serialize_request(tmp_path / "project", case, profile, editor_root=editor_root)


@pytest.fixture
def installed_artifacts():
    source_root = os.environ.get("DMD_EDITOR_SOURCE_ROOT")
    decoder_path = os.environ.get("DMD_EDITOR_DECODER_PATH")
    if not source_root or not decoder_path:
        pytest.skip("set DMD_EDITOR_SOURCE_ROOT and DMD_EDITOR_DECODER_PATH to test local staging")
    return Path(source_root), Path(decoder_path)


def test_stages_only_profile_files_and_exact_source_tree_decoder(
    installed_artifacts, profile, tmp_path,
):
    source, decoder = installed_artifacts
    staged = stage_editor(source, tmp_path / "stage", profile, decoder_path=decoder)

    editor = profile.components["ColorizingDMD editor"]
    assert set(path.name for path in staged.iterdir()) == {
        "ColorizingDMD.exe",
        "serum64.dll",
        *(Path(path).name for path in editor["dependencies"]),
    }
    assert hashlib.sha256((staged / "serum64.dll").read_bytes()).hexdigest() == PINNED_DECODER
    assert (staged / "serum64.dll").read_bytes() == decoder.read_bytes()


def test_rejects_installed_adjacent_decoder_before_launch(
    installed_artifacts, case, profile, tmp_path,
):
    source, decoder = installed_artifacts
    staged = stage_editor(source, tmp_path / "stage", profile, decoder_path=decoder)
    adjacent_dll = (source / "serum64.dll").read_bytes()
    assert hashlib.sha256(adjacent_dll).hexdigest() != PINNED_DECODER
    (staged / "serum64.dll").write_bytes(adjacent_dll)

    with pytest.raises(EditorBridgeError, match="bundled decoder.*SHA-256 mismatch"):
        write_project(tmp_path / "project", case, profile, editor_root=staged)

    assert not (tmp_path / "project").exists()


def test_stage_rejects_decoder_substitution(installed_artifacts, profile, tmp_path):
    source, _ = installed_artifacts
    staged = tmp_path / "stage"

    with pytest.raises(EditorBridgeError, match="bundled decoder.*SHA-256 mismatch"):
        stage_editor(source, staged, profile, decoder_path=source / "serum64.dll")

    assert not staged.exists()


def test_serialized_request_preserves_order_pixels_and_masks(
    installed_artifacts, case, profile, tmp_path, bridge_schema,
):
    source, decoder = installed_artifacts
    staged = stage_editor(source, tmp_path / "stage", profile, decoder_path=decoder)
    project = tmp_path / "project"
    config = tmp_path / "config"
    request = json.loads(serialize_request(
        project, case, profile, editor_root=staged, config_root=config, deadline_ms=1500,
    ))

    bridge_schema.validate(request)
    assert request["schema_version"] == 1
    assert request["expected_decoder_sha256"] == PINNED_DECODER
    assert Path(request["editor_root"]) == staged
    assert Path(request["project_root"]) == project
    assert Path(request["config_root"]) == config
    assert request["deadline_ms"] == 1500
    assert (request["width"], request["height"], request["native_shades"]) == (128, 32, 4)
    assert [ref["id"] for ref in request["references"]] == ["A", "B", "C"]
    for payload, original in zip(request["references"], case, strict=True):
        assert bytes(payload["native_pixels"]) == original.native_pixels
        assert payload["source_sha256"] == hashlib.sha256(original.native_pixels).hexdigest()
        assert payload["shape"] is False
    a, b, c = request["references"]
    assert bytes(a["ignore_bitmap"]) == bytes(b["ignore_bitmap"]) == case[0].ignore_bitmap
    assert a["native_pixels"][4:6] == [0, 1]
    assert b["native_pixels"][4:6] == [3, 2]
    assert a["ignore_sha256"] == b["ignore_sha256"] == hashlib.sha256(case[0].ignore_bitmap).hexdigest()
    assert c["ignore_bitmap"] is None
    assert c["ignore_sha256"] is None


def test_write_project_expects_missing_bridge_after_validation(
    installed_artifacts, case, profile, tmp_path,
):
    source, decoder = installed_artifacts
    staged = stage_editor(source, tmp_path / "stage", profile, decoder_path=decoder)

    with pytest.raises(EditorBridgeError, match="editor_bridge.exe.*unavailable"):
        write_project(tmp_path / "project", case, profile, editor_root=staged)


@pytest.mark.skip(reason="editor_bridge.exe is missing pending native bridge implementation")
def test_original_editor_roundtrip(case, profile):
    """Reserved for the native original-editor round-trip test."""
