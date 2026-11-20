import ctypes
import hashlib
import json
import os
import shutil
import struct
import subprocess
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
def registry_probe(tmp_path_factory):
    if os.name != "nt":
        pytest.skip("the registry transaction requires Windows")
    build = tmp_path_factory.mktemp("native-transaction")
    source = build / "probe.cpp"
    source.write_text(f'#define DMD_REPOSITORY_ROOT LR"({build})"\n' + r'''
#include <windows.h>
#include <string_view>
// Simulate a counted Win32 enumeration result that cannot be reopened
// through a null-terminated name. All actual registry I/O stays in the app hive.
void simulate_counted_name(LSTATUS status, wchar_t* name, DWORD length) {
    if (status == ERROR_SUCCESS && std::wstring_view(name, length) == L"AliasXHidden")
        name[5] = L'\0';
}
LSTATUS WINAPI probe_enum_key(HKEY k, DWORD i, LPWSTR name, LPDWORD length, LPDWORD reserved,
    LPWSTR cls, LPDWORD cls_length, PFILETIME time) {
    auto status = RegEnumKeyExW(k, i, name, length, reserved, cls, cls_length, time);
    simulate_counted_name(status, name, *length);
    return status;
}
LSTATUS WINAPI probe_enum_value(HKEY k, DWORD i, LPWSTR name, LPDWORD length, LPDWORD reserved,
    LPDWORD type, LPBYTE data, LPDWORD size) {
    auto status = RegEnumValueW(k, i, name, length, reserved, type, data, size);
    simulate_counted_name(status, name, *length);
    return status;
}
#define RegEnumKeyExW probe_enum_key
#define RegEnumValueW probe_enum_value
LSTATUS WINAPI private_open(HKEY key, LPCWSTR name, DWORD flags, REGSAM access, PHKEY result) {
    if (key == HKEY_CURRENT_USER) return ERROR_ACCESS_DENIED;
    return RegOpenKeyExW(key, name, flags, access, result);
}
#define RegOpenKeyExW private_open
#define main editor_bridge_main
#include "editor_bridge.cpp"
#undef main
int main() { return editor_bridge_main(); }
using Probe = int(__cdecl*)();
extern "C" __declspec(dllexport) const char* gate(
    HKEY software, const wchar_t* journal, const wchar_t* lock, Probe during) {
    init_apartment(apartment_type::multi_threaded);
    static std::string result;
    JsonObject observations;
    try {
        with_editor_isolation(journal, lock, [&] { return software; }, observations, [&] {
            with_journaled_transaction(software, journal, {{L"DIR_SERUM", L"temporary"}},
                observations, [&] { during(); });
            return 0;
        });
    } catch (hresult_error const& error) {
        observations.Insert(L"error", JsonValue::CreateStringValue(error.message()));
    } catch (std::exception const& error) {
        observations.Insert(L"error", JsonValue::CreateStringValue(to_hstring(error.what())));
    }
    result = to_string(observations.Stringify());
    observations = nullptr;
    clear_factory_cache();
    uninit_apartment();
    return result.c_str();
}
extern "C" __declspec(dllexport) const char* probe(
    HKEY software, const wchar_t* config, const wchar_t* project, Probe during) {
    init_apartment(apartment_type::multi_threaded);
    static std::string result;
    JsonObject observations;
    try {
        with_registry_transaction(software, fs::path(project).parent_path(), config,
            {{L"DIR_SERUM", project}}, observations, [&] {
            if (during()) throw std::runtime_error("simulated editor failure");
        });
    } catch (hresult_error const& error) {
        observations.Insert(L"error", JsonValue::CreateStringValue(error.message()));
    } catch (std::exception const& error) {
        observations.Insert(L"error", JsonValue::CreateStringValue(to_hstring(error.what())));
    }
    result = to_string(observations.Stringify());
    observations = nullptr;
    clear_factory_cache();
    uninit_apartment();
    return result.c_str();
}
''', encoding="utf-8")
    # Use the same x64 MSVC and Windows SDK required by native/CMakeLists.txt.
    locator = Path(os.environ["ProgramFiles(x86)"]) / "Microsoft Visual Studio/Installer/vswhere.exe"
    install = subprocess.check_output([
        str(locator), "-all", "-products", "*", "-property", "installationPath",
    ], text=True).splitlines()
    vcvars = next(path for root in install
                  if (path := Path(root) / "VC/Auxiliary/Build/vcvars64.bat").is_file())
    native = Path(__file__).resolve().parents[2] / "native"
    script = build / "compile.cmd"
    script.write_text(
        f'@call "{vcvars}" && cl /nologo /std:c++20 /EHsc /utf-8 /LD '
        f'/I"{native}" probe.cpp windowsapp.lib advapi32.lib /link /out:probe.dll '
        '&& link /nologo probe.obj windowsapp.lib advapi32.lib /subsystem:console /out:preflight.exe\n'
    )
    compiled = subprocess.run(["cmd", "/d", "/c", script.name], cwd=build,
                              stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    assert compiled.returncode == 0, compiled.stdout
    library = ctypes.CDLL(str(build / "probe.dll"))
    probe = library.probe
    probe.argtypes = [ctypes.c_void_p, ctypes.c_wchar_p, ctypes.c_wchar_p, ctypes.CFUNCTYPE(ctypes.c_int)]
    probe.restype = ctypes.c_char_p
    probe.gate = library.gate
    probe.gate.argtypes = probe.argtypes
    probe.gate.restype = ctypes.c_char_p
    probe.executable = build / "preflight.exe"
    return probe


def test_bridge_entry_checks_only_its_dedicated_journal(registry_probe, tmp_path):
    # A sibling artifact with a broken marker must never be replayed. Even an
    # invalid request reaches the ownership/recovery gate before preflight.
    executable = registry_probe.executable
    unrelated = executable.parent / "artifacts" / "unrelated"
    unrelated.mkdir(parents=True)
    (unrelated / "registry-incomplete.json").write_text("{}")
    result = subprocess.run([str(executable)], input=b"{}", capture_output=True, cwd=tmp_path)
    response = json.loads(result.stdout)
    assert result.returncode == 1 and response["stage"] == "request", response
    observation = response["diagnostics"]["registry_recovery"]
    assert observation["restored"] is False
    marker = Path(observation["marker_path"])
    assert marker.parent.parent == unrelated.parent / "editor-isolation-journal"
    assert marker.parent.name.startswith("S-1-")
    assert not marker.exists()


@pytest.fixture
def interrupted_editor(registry_probe, tmp_path):
    import winreg

    journal = tmp_path / "journal"
    journal.mkdir()
    run = journal / "previous"
    run.mkdir()
    snapshot = run / "registry-snapshot.json"
    snapshot.write_text(json.dumps({"schema_version": 1, "existed": True, "root_name": "ColorizingDMD",
                                    "keys": {"": {}, "Nested": {"raw": {"type": 3, "hex": "00ff"}}}}))
    marker = journal / "registry-incomplete.json"
    marker.write_text(json.dumps({"schema_version": 1, "run": run.name, "snapshot": snapshot.name,
                                  "sha256": hashlib.sha256(snapshot.read_bytes()).hexdigest()}))
    hive = ctypes.c_void_p()
    api = ctypes.windll.advapi32
    assert api.RegLoadAppKeyW(str(tmp_path / "fixture.hiv"), ctypes.byref(hive),
                              winreg.KEY_ALL_ACCESS, 1, 0) == 0
    lock = "Local\\DMD-Test-" + tmp_path.name
    called = []
    try:
        with winreg.CreateKey(hive.value, "ColorizingDMD") as key:
            winreg.SetValueEx(key, "dirty", 0, winreg.REG_SZ, "interrupted")

        @ctypes.CFUNCTYPE(ctypes.c_int)
        def operation():
            called.append(json.loads(marker.read_bytes()))
            return 0

        def invoke():
            return json.loads(registry_probe.gate(hive.value, str(journal), lock, operation))

        yield invoke, hive.value, marker, snapshot, called, lock
    finally:
        assert api.RegCloseKey(hive) == 0


def test_interrupted_registry_restored_before_new_transaction(interrupted_editor):
    import winreg

    invoke, hive, marker, snapshot, called, _ = interrupted_editor
    result = invoke()
    assert "error" not in result, result
    assert result["registry_recovery"]["restored"] is True
    assert Path(result["registry_recovery"]["snapshot_path"]) == snapshot
    assert len(called) == 1
    new_snapshot = marker.parent / called[0]["run"] / called[0]["snapshot"]
    assert new_snapshot != snapshot
    assert called[0]["sha256"] == hashlib.sha256(new_snapshot.read_bytes()).hexdigest()
    assert json.loads(new_snapshot.read_bytes()) == json.loads(snapshot.read_bytes())
    assert not marker.exists()
    with winreg.OpenKey(hive, r"ColorizingDMD\Nested") as key:
        assert winreg.QueryValueEx(key, "raw") == (b"\x00\xff", winreg.REG_BINARY)
    assert invoke()["registry_recovery"]["restored"] is False


@pytest.mark.parametrize("blocker", ["process", "owner", "snapshot", "redirect", "restore"])
def test_gate_failure_retains_marker_and_blocks_transaction(interrupted_editor, tmp_path, blocker):
    import winreg

    invoke, hive, marker, snapshot, called, lock = interrupted_editor
    process = None
    owner = None
    try:
        if blocker == "process":
            simulated = tmp_path / "ColorizingDMD.exe"
            shutil.copyfile(Path(os.environ["SystemRoot"]) / "System32/cmd.exe", simulated)
            process = subprocess.Popen([str(simulated), "/d", "/q"], stdin=subprocess.PIPE,
                                       stdout=subprocess.DEVNULL, creationflags=subprocess.CREATE_NO_WINDOW)
        elif blocker == "owner":
            create_event = ctypes.windll.kernel32.CreateEventW
            create_event.restype = ctypes.c_void_p
            owner = ctypes.c_void_p(create_event(None, True, False, lock))
            assert owner.value
        elif blocker == "snapshot":
            snapshot.write_text("{}")
        elif blocker == "redirect":
            record = json.loads(marker.read_bytes())
            record["run"] = ".."
            marker.write_text(json.dumps(record))
        else:
            # Simulate a non-restorable current key at the enumeration boundary.
            with winreg.CreateKey(hive, r"ColorizingDMD\AliasXHidden"):
                pass
        original = marker.read_bytes()
        result = invoke()
        diagnostic = {"process": "ColorizingDMD.exe", "owner": "ownership", "snapshot": "digest",
                      "redirect": "run", "restore": "embedded NUL"}[blocker]
        assert diagnostic in result["error"], result
        assert not called
        assert marker.read_bytes() == original
        assert set(marker.parent.iterdir()) == {marker, snapshot.parent}
        with winreg.OpenKey(hive, "ColorizingDMD") as key:
            assert winreg.QueryValueEx(key, "dirty") == ("interrupted", winreg.REG_SZ)
    finally:
        if process is not None:
            process.stdin.close()
            process.wait(timeout=5)
        if owner:
            assert ctypes.windll.kernel32.CloseHandle(owner)


@pytest.mark.parametrize(("exists", "callback_error"), [(True, False), (False, False), (True, True)])
def test_native_registry_transaction(registry_probe, tmp_path, exists, callback_error):
    import winreg

    config = tmp_path / "config"
    config.mkdir()
    project = tmp_path / "project"
    root = ctypes.c_void_p()
    api = ctypes.windll.advapi32
    # REG_PROCESS_APPKEY binds this fresh, file-backed hive to the pytest process.
    status = api.RegLoadAppKeyW(str(config / "fixture.hiv"), ctypes.byref(root),
                                winreg.KEY_ALL_ACCESS, 1, 0)
    assert status == 0
    key_name = "CoLoRiZiNgDmD"
    nested = key_name + r"\Nested\空"
    blob = bytes(range(256)) * 12
    snapshot = config / "registry-snapshot.json"
    marker = config / "registry-incomplete.json"
    during = []
    try:
        with winreg.CreateKey(root.value, "Sibling") as sibling:
            winreg.SetValueEx(sibling, "", 0, winreg.REG_SZ, "preserved")
        if exists:
            with winreg.CreateKey(root.value, nested) as key:
                winreg.SetValueEx(key, "", 0, winreg.REG_BINARY, blob)
                winreg.SetValueEx(key, "多", 0, winreg.REG_DWORD, 0xDEADBEEF)
            with winreg.CreateKey(root.value, key_name + r"\Empty"):
                pass
            with winreg.OpenKey(root.value, key_name, 0, winreg.KEY_WRITE) as key:
                winreg.SetValueEx(key, "DIR_SERUM", 0, winreg.REG_BINARY, b"before")

        @ctypes.CFUNCTYPE(ctypes.c_int)
        def edit():
            try:
                with winreg.OpenKey(root.value, key_name) as key:
                    setting = winreg.QueryValueEx(key, "DIR_SERUM")
                with winreg.CreateKey(root.value, key_name + r"\EditorCreated") as key:
                    winreg.SetValueEx(key, "new", 0, winreg.REG_SZ, "temporary")
                during.append((json.loads(marker.read_bytes()), json.loads(snapshot.read_bytes()), setting))
            except Exception as exc:
                during.append(exc)
                return 1
            return int(callback_error)

        response = json.loads(registry_probe(root.value, str(config), str(project), edit))
        assert len(during) == 1 and isinstance(during[0], tuple), (during, response)
        incomplete, before, temporary_value = during[0]
        assert incomplete["snapshot"] == snapshot.name
        assert before["existed"] is exists
        assert before["root_name"] == (key_name if exists else "")
        assert temporary_value == (str(project), winreg.REG_SZ)
        assert json.loads(snapshot.read_bytes()) == before
        assert not marker.exists()
        transaction = response["registry_transaction"]
        assert Path(transaction["snapshot_path"]) == snapshot
        assert Path(transaction["marker_path"]) == marker
        assert transaction["verified"] is True
        if callback_error:
            assert "simulated editor failure" in response["error"]
        else:
            assert "error" not in response
        with winreg.OpenKey(root.value, "Sibling") as key:
            assert winreg.QueryValueEx(key, "") == ("preserved", winreg.REG_SZ)
        if exists:
            assert {winreg.EnumKey(root.value, i) for i in range(2)} == {"Sibling", key_name}
            with winreg.OpenKey(root.value, nested) as key:
                assert winreg.QueryValueEx(key, "") == (blob, winreg.REG_BINARY)
                assert winreg.QueryValueEx(key, "多") == (0xDEADBEEF, winreg.REG_DWORD)
            with winreg.OpenKey(root.value, key_name) as key:
                assert winreg.QueryValueEx(key, "DIR_SERUM") == (b"before", winreg.REG_BINARY)
                assert winreg.QueryInfoKey(key)[:2] == (2, 1)
            with winreg.OpenKey(root.value, key_name + r"\Empty") as key:
                assert winreg.QueryInfoKey(key)[:2] == (0, 0)
            assert before["keys"][r"Nested\空"][""] == {"type": winreg.REG_BINARY, "hex": blob.hex()}
        else:
            with pytest.raises(FileNotFoundError):
                winreg.OpenKey(root.value, key_name)
    finally:
        assert api.RegCloseKey(root) == 0


@pytest.mark.parametrize("invalid", ["outside-run", "value-name", "subkey-name"])
def test_registry_preparation_fails_before_artifacts_or_writes(registry_probe, tmp_path, invalid):
    import winreg

    run = tmp_path / "generated-run"
    run.mkdir()
    config = (tmp_path if invalid == "outside-run" else run) / "config"
    config.mkdir()
    root = ctypes.c_void_p()
    api = ctypes.windll.advapi32
    assert api.RegLoadAppKeyW(str(run / "fixture.hiv"), ctypes.byref(root),
                              winreg.KEY_ALL_ACCESS, 1, 0) == 0
    called = []
    callback = ctypes.CFUNCTYPE(ctypes.c_int)(lambda: called.append(True) or 0)
    try:
        with winreg.CreateKey(root.value, "ColorizingDMD") as key:
            if invalid == "value-name":
                winreg.SetValueEx(key, "Alias", 0, winreg.REG_BINARY, b"preserve")
                winreg.SetValueEx(key, "AliasXHidden", 0, winreg.REG_BINARY, b"hidden")
            if invalid == "subkey-name":
                with winreg.CreateKey(key, "Alias"):
                    pass
                with winreg.CreateKey(key, "AliasXHidden"):
                    pass
        evidence = json.loads(registry_probe(root.value, str(config), str(run / "project"), callback))
        assert not called, evidence
        assert "error" in evidence
        assert list(config.iterdir()) == []
        with winreg.OpenKey(root.value, "ColorizingDMD") as key:
            assert winreg.QueryInfoKey(key)[:2] == {
                "outside-run": (0, 0), "value-name": (0, 2), "subkey-name": (2, 0),
            }[invalid]
            if invalid == "value-name":
                assert winreg.QueryValueEx(key, "Alias") == (b"preserve", winreg.REG_BINARY)
    finally:
        assert api.RegCloseKey(root) == 0


def test_registry_artifact_collision_preserves_original(registry_probe, tmp_path):
    import winreg

    root = ctypes.c_void_p()
    api = ctypes.windll.advapi32
    assert api.RegLoadAppKeyW(str(tmp_path / "fixture.hiv"), ctypes.byref(root),
                              winreg.KEY_ALL_ACCESS, 1, 0) == 0
    snapshot = tmp_path / "registry-snapshot.json"
    snapshot.write_bytes(b"earlier run")
    called = []
    callback = ctypes.CFUNCTYPE(ctypes.c_int)(lambda: called.append(True) or 0)
    try:
        evidence = json.loads(registry_probe(root.value, str(tmp_path), str(tmp_path / "project"), callback))
        assert "create registry artifact" in evidence["error"]
        assert evidence["registry_transaction"]["verified"] is False
        assert not called
        assert snapshot.read_bytes() == b"earlier run"
        assert not (tmp_path / "registry-incomplete.json").exists()
        with pytest.raises(FileNotFoundError):
            winreg.OpenKey(root.value, "ColorizingDMD")
    finally:
        assert api.RegCloseKey(root) == 0


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
    installed_artifacts, case, profile, tmp_path, monkeypatch,
):
    source, decoder = installed_artifacts
    staged = stage_editor(source, tmp_path / "stage", profile, decoder_path=decoder)

    monkeypatch.setenv("DMD_EDITOR_BRIDGE_PATH", str(tmp_path / "missing-editor_bridge.exe"))
    with pytest.raises(EditorBridgeError, match="editor_bridge.exe.*unavailable"):
        write_project(tmp_path / "project", case, profile, editor_root=staged)


@pytest.fixture
def requested_project(case, profile, tmp_path, monkeypatch):
    # Exercise process transport independently of the local vendor files.
    stage = tmp_path / "stage"
    stage.mkdir()
    monkeypatch.setattr("dmd_optimizer.adapters.editor._verify_staged_file", lambda *_: None)
    bridge = tmp_path / "editor_bridge.exe"
    bridge.touch()
    monkeypatch.setenv("DMD_EDITOR_BRIDGE_PATH", str(bridge))
    return lambda: write_project(tmp_path / "project", case, profile, editor_root=stage)


@pytest.mark.parametrize(
    ("status", "stdout", "expected"),
    [
        (0, b"", "JSON response"),
        (0, b'{"schema_version":2,"status":"ok"}', "schema version"),
        (0, b'{"schema_version":1,"status":"ok"}', "round.trip manifest"),
        (7, b"", "exit code 7"),
    ],
)
def test_bridge_rejects_unverified_results(requested_project, monkeypatch, status, stdout, expected):
    monkeypatch.setattr(subprocess, "run", lambda *a, **kw: subprocess.CompletedProcess(a, status, stdout, b""))
    with pytest.raises(EditorBridgeError, match=expected):
        requested_project()


def test_bridge_timeout_retains_diagnostics(requested_project, monkeypatch, tmp_path):
    def timeout(*args, **kwargs):
        raise subprocess.TimeoutExpired(args[0], kwargs["timeout"], output=b"started", stderr=b"partial")

    monkeypatch.setattr(subprocess, "run", timeout)
    with pytest.raises(EditorBridgeError, match="timed out"):
        requested_project()
    config = tmp_path / "project-editor-config"
    assert (config / "bridge.stdout").read_bytes() == b"started"
    assert (config / "bridge.stderr").read_bytes() == b"partial"


def test_bridge_error_exposes_registry_observations(requested_project, monkeypatch):
    diagnostics = {"registry_transaction": {"verified": False}, "editor_launched": False}
    response = {"schema_version": 1, "status": "error", "stage": "registry-restore",
                "message": "could not verify", "diagnostics": diagnostics}
    monkeypatch.setattr(subprocess, "run", lambda *a, **kw: subprocess.CompletedProcess(
        a, 1, json.dumps(response).encode(), b""))
    with pytest.raises(EditorBridgeError, match="registry-restore") as failure:
        requested_project()
    assert failure.value.diagnostics == diagnostics


def test_adapter_retains_recovery_evidence_on_unverified_manifest(requested_project, monkeypatch):
    diagnostics = {"registry_recovery": {"restored": True}}
    response = {"schema_version": 1, "status": "ok", "diagnostics": diagnostics}
    monkeypatch.setattr(subprocess, "run", lambda *a, **kw: subprocess.CompletedProcess(
        a, 0, json.dumps(response).encode(), b""))
    with pytest.raises(EditorBridgeError, match="round.trip manifest") as failure:
        requested_project()
    assert failure.value.diagnostics == diagnostics


def test_native_preflight_reports_missing_startup_texture(installed_artifacts, case, profile, tmp_path):
    if not os.environ.get("DMD_EDITOR_BRIDGE_PATH"):
        pytest.skip("set DMD_EDITOR_BRIDGE_PATH to the built x64 preflight executable")
    source, decoder = installed_artifacts
    stage = stage_editor(source, tmp_path / "stage", profile, decoder_path=decoder)
    with pytest.raises(EditorBridgeError, match=r"textures[/\\]chiffres\.raw"):
        write_project(tmp_path / "project", case, profile, editor_root=stage)
    response = json.loads((tmp_path / "project-editor-config" / "bridge.stdout").read_bytes())
    assert response["status"] == "error"
    assert response["stage"] == "startup-assets"
    assert response["diagnostics"]["editor_launched"] is False
    assert response["diagnostics"]["decoder_sha256"] == PINNED_DECODER
    assert not (tmp_path / "project").exists()


@pytest.mark.skipif(os.environ.get("DMD_EDITOR_ROUNDTRIP") != "1",
                    reason="set DMD_EDITOR_ROUNDTRIP=1 to require the original-editor round trip")
def test_original_editor_roundtrip(installed_artifacts, case, profile, tmp_path):
    source, decoder = installed_artifacts
    stage = stage_editor(source, tmp_path / "stage", profile, decoder_path=decoder)
    result = write_project(tmp_path / "project", case, profile, editor_root=stage)
    manifest = json.loads(result.manifest_path.read_bytes())
    reopened = manifest["references"]
    assert [r["id"] for r in reopened] == ["A", "B", "C"]
    assert [bytes(r["native_pixels"]) for r in reopened] == [r.native_pixels for r in case]
    assert manifest["custom_mask_count"] == 1
    assert reopened[0]["slot"] == reopened[1]["slot"] != reopened[2]["slot"]
    assert reopened[2]["slot"] == manifest["unmasked_sentinel"]
    assert result.runtime_export.is_file()
