# Task 2 Editor Round-Trip Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Prove that a generated three-reference Twister project remains editable after the pinned original ColorizingDMD editor creates, saves, reopens, and exports it.

**Architecture:** A Python adapter owns typed references and project observations; it delegates UI work to a Windows x64 bridge executable. Every bridge invocation stages an isolated, hash-verified editor tree and works only in a generated project/config directory. The bridge emits a versioned JSON manifest that the adapter validates and the integration test treats as evidence.

**Tech Stack:** Python 3.14, pytest, Windows x64 C++/Win32, original ColorizingDMD, JSON.

**Spec:** `docs/superpowers/specs/2026-11-18-task-2-editor-roundtrip-design.md`

## Global Constraints

- Use the Task 1 Twister profile: 128×32, four native shades, and normal comparison (`shape=false`).
- Stage the original editor executable and its declared dependencies into a generated directory; never modify `C:\vPinball\ColorizingDMD` or its Projects folder.
- Verify the staged decoder is source-tree Serum 2.1.0 with SHA-256 `da71fa73e838ab3e257a2a73c8f74d88a3336615930761fa494a251822e0c2d5`; never substitute the installed adjacent DLL or runtime Serum 2.5.2.
- Generated references are row-major 128×32 byte pixels in `0..3`; comparison masks are equally sized `0/1` byte arrays where `1` means ignore.
- Reference IDs are unique/nonempty. Preserve source pixels, reference order, mask assignments and hidden pixels. If the editor does not preserve IDs, persist a sidecar mapping input ID to reopened ordinal and source digest.
- Use only generated fixtures in tracked tests. Keep supplied ROM/dump and all local/editor artifacts ignored under `artifacts/<run-id>/`.
- Capture the selected editor's actual filenames, headers, field widths, endianness, defaults, slot capacity, and unmasked sentinel. Do not rely on `formats.txt` as an authoritative serializer specification.

## Review Focus

- A staged editor with the locally installed `serum64.dll` must fail before launch; own this in Task 1.
- Two references sharing a mask but differing only at hidden pixels must still reopen with their original full source pixels; own this in Task 2.
- A missing/mutated sidecar mapping must not be mistaken for stable editor IDs; own this in Task 2.
- A 65th distinct custom bitmap must fail with a recorded editor-limit diagnostic after the 64-slot probe succeeds; own this in Task 3.
- A GUI timeout, autosave, or write outside the generated sandbox must fail closed and retain diagnostics; own this in Task 3.

---

### Task 1: Define adapter types, staged-editor guard, and bridge protocol

**Files:**
- Create: `src/dmd_optimizer/__init__.py`
- Create: `src/dmd_optimizer/adapters/__init__.py`
- Create: `src/dmd_optimizer/adapters/editor.py`
- Create: `schemas/editor-bridge-v1.json`
- Create: `tests/integration/test_editor_roundtrip.py`
- Modify: `pyproject.toml`

**Interfaces:**
- Consumes: `Profile` from `scripts.lock_profile`, an explicit staged-editor root, generated references.
- Produces: `Reference`, `ProjectFiles`, `EditorBridgeError`, and `write_project(folder: Path, refs: Sequence[Reference], profile: Profile) -> ProjectFiles`.

- [ ] **Step 1: Write failing generated-fixture tests**

Create a `case` fixture with three row-major 4096-byte frames A/B/C (`0..3`), unique IDs, `shape=False`, and a nontrivial 4096-byte shared mask for A/B. Make A/B differ both in compared and ignored positions; give C `mask=None`. Assert invalid geometry, shade, duplicate/empty IDs, non-binary masks, and missing staged root are rejected before bridge launch.

- [ ] **Step 2: Run the focused tests and confirm the adapter is absent**

Run: `.\\venv\\Scripts\\python.exe -m pytest tests\\integration\\test_editor_roundtrip.py -q`

Expected: FAIL because `dmd_optimizer.adapters.editor` and `write_project` do not exist.

- [ ] **Step 3: Implement types and request validation**

Define immutable `Reference(id: str, native_pixels: bytes, ignore_bitmap: bytes | None, shape: bool = False)` and `ProjectFiles(root: Path, manifest_path: Path, runtime_export: Path | None, observations: Mapping[str, object])`. Validate against `profile.width`, `profile.height`, and `profile.native_shades`. Define a versioned JSON request/response schema; include source digests, expected decoder digest, explicit editor root, isolated config root, project root, and deadline.

- [ ] **Step 4: Implement isolated staging guard**

Add `stage_editor(source_root: Path, destination: Path, profile: Profile) -> Path`. Copy only profile-declared editor files plus the locked source-tree decoder artifact. Verify every copied digest before launch, including decoder SHA-256 `da71fa...c2d5`; raise `EditorBridgeError` naming the mismatched component. Never write under the source root.

- [ ] **Step 5: Verify validation and staging tests**

Run: `.\\venv\\Scripts\\python.exe -m pytest tests\\integration\\test_editor_roundtrip.py -q`

Expected: adapter validation/staging tests pass; bridge-dependent tests remain expected failures/skips with an explicit missing-bridge reason.

- [ ] **Step 6: Commit**

```powershell
git add pyproject.toml src/dmd_optimizer schemas/editor-bridge-v1.json tests/integration/test_editor_roundtrip.py
git commit -m "feat: define editor bridge adapter contract"
```

### Task 2: Build the deterministic original-editor bridge and round-trip manifest

**Files:**
- Create: `native/CMakeLists.txt`
- Create: `native/editor_bridge.cpp`
- Modify: `src/dmd_optimizer/adapters/editor.py`
- Modify: `tests/integration/test_editor_roundtrip.py`

**Interfaces:**
- Consumes: the v1 request produced by `write_project`.
- Produces: `editor_bridge.exe` and a v1 JSON manifest describing companion files, reopened references, sidecar mapping, slot assignments, sentinel, headers, and export path.

- [ ] **Step 1: Add failing bridge-result tests**

Make the generated test call `write_project`. Assert `case.reopened.source_pixels == case.input_pixels`, `case.reopened.custom_mask_count == 1`, A/B share exactly one bitmap, C is unmasked, order is A/B/C, hidden source pixels are retained, and the sidecar maps every input ID to its reopened ordinal/source digest. Add missing/changed manifest, timeout, and nonzero bridge exit cases.

- [ ] **Step 2: Run and confirm bridge round trip fails**

Run: `.\\venv\\Scripts\\python.exe -m pytest tests\\integration\\test_editor_roundtrip.py -q`

Expected: FAIL because no `editor_bridge.exe` exists or no manifest can be produced.

- [ ] **Step 3: Implement bounded native bridge**

Build an x64 Windows bridge with CMake/Visual Studio tools. It reads one JSON request from stdin or a request file and emits one JSON response. It launches only the staged executable with redirected working/config/autosave/project locations; waits no longer than the requested deadline; captures exit code/stdout/stderr/window diagnostics; and terminates only its child on timeout. Implement the smallest deterministic UI sequence required to create/import the fixture, assign masks, open, fresh-save, reopen in a new editor process, and export runtime files.

- [ ] **Step 4: Implement manifest and adapter inspection**

Manifest every generated companion file with path, SHA-256, size, and observed header metadata. Record source pixel/mask digests, ordinal, shape flag, slot/sentinel, and runtime export. Write the optimizer sidecar if no stable ID exists in the reopened editor payload. The Python adapter must reject incomplete manifests, files outside the sandbox, changed source digests, changed mask sharing, or invalid export paths.

- [ ] **Step 5: Verify full generated round trip**

Run: `.\\venv\\Scripts\\python.exe -m pytest tests\\integration\\test_editor_roundtrip.py -q`

Expected: all generated round-trip tests pass on Windows; a missing editor/automation capability fails with a preserved diagnostic rather than a direct-writer fallback.

- [ ] **Step 6: Commit**

```powershell
git add native src/dmd_optimizer tests/integration/test_editor_roundtrip.py
git commit -m "feat: add original editor round-trip bridge"
```

### Task 3: Establish selected-build limits, golden package, and local evidence

**Files:**
- Create: `tests/fixtures/editor_roundtrip/golden/`
- Modify: `tests/integration/test_editor_roundtrip.py`
- Create: `docs/superpowers/evidence/task-2-editor-roundtrip.md`
- Create: `artifacts/<run-id>/editor-roundtrip.log`
- Create: `artifacts/<run-id>/editor-roundtrip-evidence.json`

**Interfaces:**
- Consumes: Task 2 bridge manifest and the pinned staged editor.
- Produces: a tracked synthetic golden package, evidence of selected-build limits, and a passing editor/native-loader smoke workflow.

- [ ] **Step 1: Add the 64/65 boundary and loader smoke tests**

Generate 64 references each with a distinct mask and assert save/reopen preserves 64 slots. Generate a 65th distinct mask and assert an explicit editor limit error/diagnostic. Add a smoke test that loads the bridge export with the staged pinned 2.1.0 decoder without asserting matching semantics; reserve matching behavior for Task 3.

- [ ] **Step 2: Run and confirm absent limits/evidence fail**

Run: `.\\venv\\Scripts\\python.exe -m pytest tests\\integration\\test_editor_roundtrip.py -q`

Expected: FAIL until the boundary probe and native-loader smoke evidence are implemented.

- [ ] **Step 3: Record observed build behavior**

Run the 3-reference round trip and 64/65 probe in a new artifact directory. Record command, exit code, staged binary hashes, companion names, headers, field widths, endianness, defaults, observed `255` unmasked sentinel, 64-slot limit, and generated package hashes. Copy only the generated 3-reference package and its manifest into `tests/fixtures/editor_roundtrip/golden/`.

- [ ] **Step 4: Verify the complete Task 2 suite**

Run: `.\\venv\\Scripts\\python.exe -m pytest tests\\integration\\test_profile.py tests\\integration\\test_editor_roundtrip.py -q`

Expected: PASS with no skipped editor test. Confirm the golden package is reopened by the staged editor in a fresh process and the staged decoder accepts the exported runtime file.

- [ ] **Step 5: Commit**

```powershell
git add tests/fixtures/editor_roundtrip tests/integration/test_editor_roundtrip.py docs/superpowers/evidence/task-2-editor-roundtrip.md
git commit -m "test: record editor round-trip compatibility evidence"
```

## Execution Handoff

Execute with subagent-driven development. Each task requires an independent review before moving to the next. A failure to operate the pinned editor bridge is a hard block with preserved evidence; do not substitute a direct serializer without a new approved design.
