# Task 2 Registry Isolation Recovery Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Run the staged ColorizingDMD editor without permanently changing the current user's ColorizingDMD settings, including after an interrupted bridge run.

**Architecture:** The native bridge owns the Windows-registry transaction because it launches the editor. It snapshots the complete `HKCU\\SOFTWARE\\ColorizingDMD` subtree into the generated run directory, writes minimal temporary values, and restores/verifies the snapshot after the child exits. Python owns durable incomplete-run detection before every new bridge invocation.

**Tech Stack:** Python 3.14, pytest, Windows x64 C++/Win32 Registry APIs, original ColorizingDMD.

**Spec:** `docs/superpowers/specs/2026-11-18-task-2-editor-roundtrip-design.md`

## Global Constraints

- Use `C:\\DMD Colorization\\ColorizingDMD` only as a read-only staging source; never modify it, `C:\\vPinball\\ColorizingDMD`, or either `Projects` directory.
- Stage and SHA-256-verify required startup assets, beginning with `textures\\chiffres.raw`, plus the locked 2.1.0 decoder SHA-256 `da71fa73e838ab3e257a2a73c8f74d88a3336615930761fa494a251822e0c2d5`.
- Never trust an adjacent `serum64.dll` merely because it is present.
- Snapshot, restore, and verify only `HKCU\\SOFTWARE\\ColorizingDMD`; preserve value names, types, binary data, subkeys, and pre-run absence/presence.
- Refuse concurrent ColorizingDMD use and retain recovery artifacts only under ignored `artifacts/<run-id>/` paths.
- A failed preparation, launch, cleanup, or verification must fail closed and preserve diagnostics; it must not claim a successful round trip.

## Review Focus

- A pre-existing registry subtree with nested keys and binary values must be restored byte-for-byte after a normal run; Task 1 owns this test.
- An absent subtree must be absent again after cleanup; Task 1 owns this test.
- An interrupted run marker must restore before a later launch, while a live lock must prevent concurrent recovery; Task 2 owns this test.
- A running ColorizingDMD process must block a run before any registry write; Task 2 owns this test.
- Missing or changed startup assets must fail before registry mutation or launch; Task 3 owns this test.

---

### Task 1: Implement and verify normal registry transaction

**Files:**
- Modify: `native/editor_bridge.cpp`
- Modify: `src/dmd_optimizer/adapters/editor.py`
- Modify: `tests/integration/test_editor_roundtrip.py`

**Interfaces:**
- Consumes: bridge request `config_root` and generated run root.
- Produces: `registry-snapshot.json`, `registry-incomplete.json`, and manifest `registry_transaction` observations.

- [ ] **Step 1: Write failing transaction tests**

Add tests that construct a disposable ColorizingDMD registry fixture through an injectable registry abstraction, run snapshot → temporary values → restore, and assert nested values, registry types, raw bytes, and absent-key state are identical before and after. Assert snapshot/marker paths remain inside the generated run root.

- [ ] **Step 2: Run tests to confirm the transaction is absent**

Run: `.\\venv\\Scripts\\python.exe -m pytest tests\\integration\\test_editor_roundtrip.py -q`

Expected: FAIL because normal registry transaction evidence is unavailable.

- [ ] **Step 3: Implement native snapshot and restoration**

Implement Win32 recursive enumeration with `RegOpenKeyExW`, `RegEnumKeyExW`, `RegEnumValueW`, `RegSetValueExW`, and deletion of only the target subtree. Serialize names, types, and binary data into the run-local snapshot. Create the incomplete marker before the first write; restore in cleanup; verify via a fresh enumeration; then remove the marker only after verification succeeds.

- [ ] **Step 4: Run focused verification**

Run: `.\\venv\\Scripts\\python.exe -m pytest tests\\integration\\test_editor_roundtrip.py -q`

Expected: transaction tests pass; native editor acceptance remains opt-in.

- [ ] **Step 5: Commit**

Commit message: `feat: isolate editor registry settings`

### Task 2: Add exclusive-use and crash recovery gate

**Files:**
- Modify: `native/editor_bridge.cpp`
- Modify: `src/dmd_optimizer/adapters/editor.py`
- Modify: `tests/integration/test_editor_roundtrip.py`

**Interfaces:**
- Consumes: durable incomplete marker and a named/run-local bridge lock.
- Produces: recovery observation stating whether restoration occurred before launch.

- [ ] **Step 1: Write failing exclusive-use and recovery tests**

Add tests for: a simulated running `ColorizingDMD.exe` rejecting before registry mutation; a stale incomplete marker restoring its snapshot before a new launch; an active lock rejecting recovery; and failed restoration retaining the marker and blocking launch.

- [ ] **Step 2: Run tests to confirm the gate is absent**

Run: `.\\venv\\Scripts\\python.exe -m pytest tests\\integration\\test_editor_roundtrip.py -q`

Expected: FAIL because interrupted-run recovery is unavailable.

- [ ] **Step 3: Implement recovery gate**

Before staging/launch, acquire exclusive bridge ownership, detect a prior incomplete marker, restore and verify it, and record recovery in the response. Detect an existing ColorizingDMD process before the registry snapshot. On any error, retain the marker and diagnostics and do not launch the editor.

- [ ] **Step 4: Run focused and full verification**

Run: `.\\venv\\Scripts\\python.exe -m pytest tests\\integration\\test_editor_roundtrip.py -q`

Run: `.\\venv\\Scripts\\python.exe -m pytest -q`

Expected: both pass except deliberately opt-in real-editor acceptance tests until Task 3 resumes.

- [ ] **Step 5: Commit**

Commit message: `feat: recover interrupted editor isolation`

### Task 3: Lock startup assets and run a safe editor preflight

**Files:**
- Modify: `scripts/lock_profile.py`
- Modify: `tests/integration/test_editor_roundtrip.py`
- Modify: `native/editor_bridge.cpp`
- Create: `docs/superpowers/evidence/task-2-isolation-preflight.md`

**Interfaces:**
- Consumes: second-installation source root and declared startup-asset lock entries.
- Produces: staged startup assets and a preflight manifest proving registry state was restored.

- [ ] **Step 1: Write failing staging and restoration tests**

Add tests that a missing/mutated `textures\\chiffres.raw` fails before registry preparation and that a real staged preflight records matching asset hashes plus verified registry restoration.

- [ ] **Step 2: Run tests to confirm assets are not yet locked**

Run: `.\\venv\\Scripts\\python.exe -m pytest tests\\integration\\test_editor_roundtrip.py -q`

Expected: FAIL because the startup asset is not profile-declared and verified.

- [ ] **Step 3: Implement asset lock and preflight evidence**

Add profile support for non-binary startup assets with SHA-256 verification, stage `textures\\chiffres.raw` from the read-only second installation, and record its digest/size in the manifest. Run only a bounded startup preflight; cleanup must restore the registry before reporting its result.

- [ ] **Step 4: Verify and record evidence**

Run: `.\\venv\\Scripts\\python.exe -m pytest tests\\integration\\test_editor_roundtrip.py -q`

Run: `.\\venv\\Scripts\\python.exe -m pytest -q`

Expected: all isolation tests pass; the real-editor preflight either reaches a documented next capability boundary with verified cleanup or fails with preserved diagnostics.

- [ ] **Step 5: Commit**

Commit message: `test: lock editor startup assets`

## Execution Handoff

Execute subagent-driven, with an independent review after every task. Once this plan is complete, resume the blocked Task 2 round-trip plan at its native editor launch step; do not weaken the staging or recovery requirements.
