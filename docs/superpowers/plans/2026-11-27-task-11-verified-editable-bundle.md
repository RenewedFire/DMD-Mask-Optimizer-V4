# Task 11 Verified Editable Bundle Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking. Leave changes uncommitted for the user's manual commit.

**Goal:** Publish an editable original ColorizingDMD project and separate, reconciled exports only for a scope that the pinned editor and native runtime actually verify; otherwise publish an explicit diagnostic/source bundle.

**Architecture:** Read and validate the immutable Task 10 solution, Task 9 pool and families, and Task 5 corpus revision. Preflight reference and mask counts and the existing bridge's request limits before any editor operation. Compile stable reference and mask mappings in a fresh staging folder, verify serialized native output against ordered corpus replay, then atomically publish a fresh bundle with per-occurrence accounting. A failed or oversized full export yields diagnostics; a smaller subset is publishable only after its omissions and known negative inputs pass verification.

**Tech Stack:** Python 3.11+, pytest, SQLite corpus, existing original-editor bridge and isolated Serum runtime worker, canonical JSON/CSV, HTML report.

**Spec:** `DMD_Mask_Optimizer_Design_and_Implementation_Plan.md` §§11, 14, 18; `docs/superpowers/plans/2026-11-18-dmd-mask-optimizer.md` Task 11; `docs/superpowers/plans/2026-11-25-task-10-feasible-assignment.md`; `AGENTS.md`.

## Global Constraints

- Reuse `artifacts/task9-static-analysis-01/corpus`, `artifacts/task9-static-analysis-02/{families,options}.json`, and `artifacts/task10-static-solve-02/solution.json`. The source `twst_405.txt` is fixed at SHA-256 `f711aec5d42fdc423ca02bfd2c8f05c158afaee27a97acdbf59d532b81095b11`. Only create one worktree-local immutable import if the capture is unavailable.
- Do not use an interactive qualification, VPinMAME/ColorizingDMD session, recorder, watcher, or live intake to analyze the static dump. Direct corpus analysis and ordinary tests determine scope and preflight. The pinned editor/runtime bridge is used only to verify a staged export when preflight establishes a representable fixture, with its existing backup/restore isolation.
- Task 9 has 10,301 exact observed-only families, one unmasked option each, and no custom-mask alternatives. Task 10's zero-mask optimum is pool-scoped. Do not describe it as mask savings or full-ROM coverage; preserve every exact frame and explain reference-budget failures.
- Never silently trim the 10,301 families. Every one of the 14,443 stored occurrences receives a mapping or a specific omission reason. A subset is labeled provisional and tested against omitted known inputs; if omitted inputs collide with retained rules, publish diagnostics only.
- A staged editable project must round-trip through the pinned original editor and its runtime export must load and replay in the pinned Serum worker. Preserve raw native pixels, mask polarity, stable source IDs, ordering, author-edit state, and companion-file hashes. Avoid touching existing colorization projects or installations.
- Do not overwrite a prior run or a user-edited output. Publish to a fresh run directory by atomic rename after verification. Report source revision, profile, pool, solution, native export digest, tested domain, unknowns, mismatches, and stop/failure reason separately.

## Review Focus

1. Full exact pool exceeds a bridge or editor limit: preflight reports the exact limiting constraint before writing a misleading project; test the 10,301-reference handoff against the measured limits.
2. A subset omits a known frame that matches a retained reference: reject the subset or mark it unresolved; test an adversarial known negative.
3. Same visual frame occurs after reset or with different prior match: ordered replay retains session/reset context; test both sequences.
4. An old or tampered pool, solution, corpus revision, editor export, or file digest: refuse publication and preserve the earlier output; test each identity boundary.
5. Failure during editor save, native replay, file write, or final rename: leave no published partial bundle and preserve author edits; inject each failure.

---

### Task 1: Lock export inputs and measure capacity

**Files:** Create `src/dmd_optimizer/export/model.py`, `src/dmd_optimizer/export/preflight.py`, `tests/unit/test_export_preflight.py`; modify `native/editor_bridge.cpp` only if a verified fixture demonstrates a safe bridge limit change.

**Interfaces:** `preflight(result: SolveResult, pool: OptionPool, families: FamilySet, revision: Revision, *, bridge_limit_bytes: int = 16_777_216) -> ExportDecision`. `ExportDecision` records identity digests, requested/representable reference counts, mask count, serialized request estimate, exact limits, and `full_export_possible` with reasons.

- [ ] **Step 1: Write failing tests** for the current 10,301-reference pool, a small representable fixture, 64/65 masks, stale revision/profile/pool/solution, and request-size boundary. Assert the actual limiting value is reported and no family is dropped.
- [ ] **Step 2: Run** `uv run --group test pytest tests/unit/test_export_preflight.py -q`; expect failure from missing preflight behavior.
- [ ] **Step 3: Implement** identity validation by reopening the Task 10 solution and Task 9 handoff; derive limits from the pinned bridge/editor/runtime evidence, including the current 16 MiB bridge input ceiling and runtime count field. Measure the encoded request using the actual serializer rather than a guessed per-reference size. Do not expand a limit without a separate passing pinned-editor fixture.
- [ ] **Step 4: Rerun** the focused tests; require all pass. Record the exact full-pool capacity verdict in the Task 11 progress ledger.

### Task 2: Compile stable outputs and reconcile occurrences

**Files:** Create `src/dmd_optimizer/export/compile.py`, `src/dmd_optimizer/export/files.py`, `tests/unit/test_export_compile.py`.

**Interfaces:** `compile_selection(decision: ExportDecision, selected_family_ids: frozenset[str], corpus_path: Path) -> CompiledSelection`; `write_separate_exports(compiled: CompiledSelection, folder: Path) -> ExportInventory`. Keep stable family/option IDs and an explicit native ordinal mapping.

- [ ] **Step 1: Write failing tests** for deterministic mask slots/reference order, exact raw four-shade payloads and lossless previews, all 14,443 occurrence rows, repeat/session/offset preservation, and explicit omissions for a strict subset.
- [ ] **Step 2: Run** `uv run --group test pytest tests/unit/test_export_compile.py -q`; expect failure from missing compiler/writer.
- [ ] **Step 3: Implement** `masks.json`, lossless `masks/` and `reference_frames/` outputs, `frame_mapping.csv`, `optimization.json`, `coverage.json`, and escaped `report.html`. Include geometry, polarity, stable IDs, slot/ordinal mappings, identity digests, proof scope, uncertainty, and per-file hashes. Reject duplicate IDs, invalid pixels, and row-count mismatch.
- [ ] **Step 4: Rerun** focused tests; require exact semantic and checksum assertions to pass.

### Task 3: Verify native publication eligibility

**Files:** Create `src/dmd_optimizer/verify/exported.py`, extend `src/dmd_optimizer/adapters/editor.py` and the bridge only as required by a small passing fixture; create `tests/integration/test_export.py`.

**Interfaces:** `verify_export(compiled: CompiledSelection, project: ProjectFiles, corpus_path: Path, profile: Profile) -> VerificationRecord`. The record includes input/mapped/omitted occurrences, wrong-family matches, unknown matches, tested resets and variants, native export digest, and failure witnesses.

- [ ] **Step 1: Write failing integration tests** beginning with `wrong_family_matches == 0`, `mapped_occurrences + omitted_occurrences == input_occurrences`, and `author_edit_preserved`. Include omitted known negatives, reordered references, reset/repeat sequences, runtime CRC collision, corrupted native bytes, and editor round-trip failure.
- [ ] **Step 2: Run** `uv run --group test pytest tests/integration/test_export.py -q`; expect missing verifier/bridge behavior.
- [ ] **Step 3: Extend** the pinned bridge's three-reference fixture path to accept a bounded staged selection while retaining isolated config and registry backup/restore. Reopen/save/export, reload final bytes through the existing worker, and replay ordered corpus sessions plus supported domain variants. Verify native ordinal-to-stable-ID mapping and source pixel preservation. If editor invocation cannot be supported safely, record the constraint and keep native publication disabled.
- [ ] **Step 4: Rerun** focused integration tests; require zero unexplained wrong-family matches and no publishable status for failing fixtures.

### Task 4: Publish atomically and qualify the fixed Twister handoff

**Files:** Create `src/dmd_optimizer/export/publish.py`, `scripts/publish_verified_bundle.py`, `docs/superpowers/evidence/task-11-verified-editable-bundle.md`; extend `tests/integration/test_export.py`.

**Interfaces:** `publish(result: SolveResult, revision: Revision, folder: Path) -> ExportRecord`, with explicit Task 9 paths/profile/corpus passed through a configuration object or CLI. `ExportRecord` identifies `verified-editable`, `verified-subset`, or `diagnostic-only`, final inventory/hash, coverage, and reasons.

- [ ] **Step 1: Write failing tests** for fresh-directory publication, repeatable contents, no overwrite of edited output, injected disk/reopen/replay/rename failure, and diagnostic-only fallback when full and safe subset exports cannot be verified.
- [ ] **Step 2: Run** `uv run --group test pytest tests/integration/test_export.py -q`; expect missing publish behavior.
- [ ] **Step 3: Implement** staging, inventory hashing, read-back, full-scope attempt, and deterministic subset selection only when the omitted known negatives pass verification. Otherwise publish source/diagnostic outputs with explicit reference-limit and recognition reasons. Atomically promote only a verified stage to a fresh run directory; keep failed stage diagnostics separately and never replace an author-edited project.
- [ ] **Step 4: Rerun** focused tests. Run one direct static-handoff qualification using the existing corpus and manifests; capture the exact capacity verdict, published status, mappings, native digest if present, and all failure witnesses. Do not present a diagnostic bundle as an editable project.
- [ ] **Step 5: Run** `uv run --group test pytest -q --junitxml=artifacts/task11-<run-id>/suite.xml` and `git diff --check`; require zero failures/errors. Perform one independent code review and resolve correctness findings. Save evidence and progress locally, synchronize plan/evidence to the main project's `docs/superpowers/` folder, and leave changes uncommitted.

## Completion

Task 11 is complete when every fixed-dump occurrence is accounted for; the exact full-pool capacity verdict is measured; any published editable project has passed editor reopen/export and native ordered replay with zero unexplained wrong-family matches; any subset is explicit and rejects omitted known negatives; and unavailable native publication produces a truthful diagnostic bundle. Full-ROM completeness and mask savings remain outside this task's proof scope.
