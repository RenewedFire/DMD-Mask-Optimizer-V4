# Task 1 Local Runtime Baseline Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make Task 1 reproducibly lock the active local VPinMAME runtime while explicitly recording the absent upstream archive digest.

**Architecture:** Extend the native-component profile schema with local-installation provenance, then validate that declaration in the existing profile loader and lock verifier. The active user-provided DLLs become the immutable local-runtime fixture baseline; their hashes, x64 PE architecture, and numeric Windows VERSIONINFO file versions are checked at lock time. The original editor/decoder remains a separate authoring scope.

**Tech Stack:** Python 3.11+, pytest, Windows PE metadata, JSON profile.

**Spec:** `docs/superpowers/specs/2026-11-18-task-1-local-runtime-baseline-design.md`

## Global Constraints

- Do not modify files below `C:\vPinball`.
- Keep the Twister ROM and dump SHA-256 checks unchanged.
- Never report upstream-release byte identity unless the official archive is available and hashed.
- The local baseline is the active `C:\vPinball\VisualPinball\VPinMAME` directory.

## Review Focus

- A component with an absent archive hash but no `local-installation` provenance must fail validation.
- A local baseline with an empty or non-absolute installation path must fail validation.
- A DLL substituted after profile creation must fail the SHA-256 check.
- An x86 replacement DLL must fail the x64 architecture check even if its hash is updated.
- A local Serum 2.5.2 lock must not be interpreted as legacy editor-matching parity.

---

### Task 1: Local-baseline profile validation

**Files:**
- Modify: `profiles/twst_405.json`
- Modify: `scripts/lock_profile.py`
- Modify: `tests/integration/test_profile.py`

**Interfaces:**
- Consumes: component JSON records in `profiles/twst_405.json`.
- Produces: `lock_profile(rom: Path, dump: Path, toolchain: Path, scope="local-runtime") -> Profile` that verifies one explicit scope. A local-runtime pass leaves `authoring_binaries_verified` and `native_binaries_verified` false.

- [ ] **Step 1: Write failing tests for the local provenance contract**

Add tests asserting that an archive-less component is rejected unless
`provenance.kind == "local-installation"` and `provenance.installation_path`
is an absolute Windows path. Add a test asserting the local Serum 2.5.2
record locks only after its file digest and x64 architecture pass.

- [ ] **Step 2: Run the focused tests and verify failure**

Run: `python -m pytest tests/integration/test_profile.py -q`

Expected: FAIL because the profile schema does not yet recognize the local
provenance declaration.

- [ ] **Step 3: Implement local provenance validation in `scripts/lock_profile.py`**

Validate `provenance` as an object. Permit a null `release_archive_sha256`
only for `kind == "local-installation"` with a non-empty absolute Windows
`installation_path`; otherwise retain the existing SHA-256 requirement.

- [ ] **Step 4: Update `profiles/twst_405.json` with the active DLL baseline**

Set the VPinMAME components to the active versions and SHA-256 values observed
in `C:\vPinball\VisualPinball\VPinMAME`: VPinMAME 3.6.0.1227,
Bass 2.4.17, and Serum 2.5.2. Record the absent official archive digest as a
provenance limitation; do not remove the runtime-parity limitation.

- [ ] **Step 5: Run focused tests and verify pass**

Run: `python -m pytest tests/integration/test_profile.py -q`

Expected: PASS.

### Task 2: Native lock evidence

**Files:**
- Modify: `artifacts/2026-11-18-task-1-fix-3/fixture-profile.json`
- Create: `artifacts/2026-11-18-task-1-fix-3/native-lock.log`
- Create: `artifacts/2026-11-18-task-1-fix-3/evidence.json`

**Interfaces:**
- Consumes: the validated Task 1 profile and copied test toolchain.
- Produces: audit evidence for the local runtime baseline.

- [ ] **Step 1: Write a failing integration assertion for the exact active local baseline**

Add a locally gated test that invokes `lock_profile` against a staged copy of
the active VPinMAME DLL directory and asserts `local_runtime_verified is True`, `authoring_binaries_verified is False`, and `native_binaries_verified is False`; then corrupt one staged DLL and assert a SHA-256 failure.

- [ ] **Step 2: Run the assertion and verify failure before staging support exists**

Run: `DMD_LOCAL_RUNTIME=1 python -m pytest tests/integration/test_profile.py -q`

Expected: FAIL until the profile paths/provenance and staged layout agree.

- [ ] **Step 3: Stage only the declared binaries into the Task 1 evidence directory**

Copy `VPinMAME64.dll`, `Bass64.dll`, and `serum64.dll` into the evidence
toolchain; do not modify their source files under `C:\vPinball`.

- [ ] **Step 4: Run the full suite and native lock**

Run: `DMD_LOCAL_RUNTIME=1 python -m pytest -q` and
`python scripts/lock_profile.py --rom twst_405.zip --dump twst_405.txt --toolchain artifacts/2026-11-18-task-1-fix-3/toolchain --scope local-runtime`.

Expected: tests pass and the local-runtime lock emits `local_runtime_verified: true`, `authoring_binaries_verified: false`, and `native_binaries_verified: false`. A separate staged `--scope authoring` run is required before authoring parity can be asserted.

- [ ] **Step 5: Record command results, file hashes, and limitations in evidence**

Write evidence that identifies the exact local source paths, staged hashes,
test commands, exits, and the explicit non-claim of upstream-archive byte identity or editor/runtime parity, plus the selected lock scope and its unverified counterpart.
