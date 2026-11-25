# Task 3 Native Matching Oracle Implementation Plan

> **For agentic workers:** Use superpowers:executing-plans for one implementation pass, followed by one independent milestone review. Steps use checkbox syntax for tracking. This efficiency convention follows the user's explicit direction to reduce repeated agent/review cycles.

**Goal:** Certify native reference recognition and observable renderer behavior for an unchanged export from the selected original editor.

**Architecture:** Python validates inputs and drives a bounded native worker with one decoder instance per process. Production and observer runs consume identical event sequences; observer IDs must not change renderer results. Exact editor exports are the acceptance authority; modified diagnostic packages establish hypotheses only.

**Tech Stack:** Python 3.14, pytest, Windows x64 C++, pinned Serum DLL, existing worker protocol.

**Spec:** `DMD_Mask_Optimizer_Design_and_Implementation_Plan.md`, matching and compatibility requirements; `docs/superpowers/plans/2026-11-18-dmd-mask-optimizer.md`, Task 3.

## Current checkpoint — do not reimplement

Commit `e967718` already provides `native/serum_worker.cpp`, `src/dmd_optimizer/verify/oracle.py`, `schemas/worker-v1.json`, and `tests/integration/test_oracle.py`. Nine focused oracle tests passed with the pinned decoder. The evidence is in `docs/superpowers/evidence/task-3-native-oracle.md`.

The untouched Task 2 runtime archive has SHA-256 `06c2c489aae7d55fec68e1648b88192c842d3ac30bd114201487c48d49df5271`. Its editor writes hashes at byte 106, while the pinned Serum 2.1.0 decoder reads them at byte 102. Loading alone previously passed but actual recognition failed or faulted. The current oracle rejects that layout before replay. A diagnostic copy removing four bytes demonstrated matching behavior, but does not certify the original export.

## Global constraints

- Twister `twst_405`, 128 by 32 row-major bytes, native shades 0 through 3, `shape=false`; ignore bit 1 omits a pixel from comparison.
- Preserve exact input export bytes and hashes. Never silently repair an archive in production replay.
- Current decoder lock is SHA-256 `da71fa73e838ab3e257a2a73c8f74d88a3336615930761fa494a251822e0c2d5`. A different binary requires an explicit compatibility-profile revision and supporting evidence.
- Keep existing projects and installed editor files untouched. Local binaries, probes, and logs stay under `artifacts/task3-<run-id>/`; tracked fixtures are synthetic only.
- The unfinished 64/65-mask UI probe is a separate Task 2 obligation, not a prerequisite for these three-reference matching tests.
- Run focused tests during changes, the full suite once at the milestone, and one final independent review. Reuse existing build/dependency commands from the evidence file; do not reinstall the environment or restart UI discovery.

## Review focus

- Successful native load with broken recognition must fail certification (step 2).
- Diagnostic layout changes must never enter production replay silently (steps 1 and 2).
- Repeated frames and unknowns may share native result codes; preserve observable state and label inferred IDs (step 3).
- CRC collisions differ from equal compared bytes and must remain distinguishable (step 3).
- Timeout/reset must isolate worker state and leave another worker operational (step 3).

---

### Step 1: Confirm the existing oracle contract

**Files:** existing `src/dmd_optimizer/verify/oracle.py`, `native/serum_worker.cpp`, `schemas/worker-v1.json`, `tests/integration/test_oracle.py`.

**Interface:** `replay(project: ProjectFiles, events: Iterable[ReplayEvent], profile: Profile, *, instrument=True) -> Iterator[Match]`. Events are `Reset`, `AdvanceTime(milliseconds)`, and `Frame(pixels)`. Matches retain stable reference or unknown, ID origin, and native output metadata.

- [ ] Read the checkpoint evidence and existing tests once; record current commit, worker build command, decoder digest, and export digest in one task status file.
- [ ] Run `python -m pytest tests/integration/test_oracle.py -q -p no:cacheprovider` with the already documented worker and decoder paths. Record separately which tests use diagnostic derivatives.
- [ ] Add a failing regression only for a missing contract requirement. Retain existing packet-version/length, geometry, shade, reset, shutdown, and isolated-timeout tests; avoid rebuilding proven infrastructure.

**Deliverable:** a reproducible baseline and an exact list of remaining certification failures.

### Step 2: Resolve the editor/decoder compatibility gap

**Files:** `profiles/twst_405.json`, `scripts/lock_profile.py`, `tests/integration/test_oracle.py`, and `docs/superpowers/evidence/task-3-native-oracle.md`; change only files needed by the chosen resolution. Any additional build recipe belongs under `scripts/` and must name exact source revision and compiler options.

- [ ] Use existing serializer/reader evidence to identify the smallest supported compatible pair. First check whether the selected editor offers an export mode accepted by the existing decoder. Otherwise identify a source-matched decoder or a reproducibly built layout correction; do not try arbitrary adjacent DLLs.
- [ ] Before implementation, write the acceptance regression: an untouched editor-generated archive must replay A, B, and C correctly from reset and produce distinguishable expected renderer outputs.
- [ ] If the resolution changes the pinned component or supported format, document the exact proposed pair, provenance, new hashes, and affected claims for user approval before activating that profile. Continue preparing reproducible diagnostic evidence while approval is pending.
- [ ] Implement only the approved compatibility resolution. Preserve the old mismatch fixture as a rejection regression and record the new untouched export's digest.
- [ ] Run the focused oracle suite. Require native recognition, not just `Serum_Load` acceptance, on unchanged editor output. If no compatible pair is established, record Task 3 as blocked and retain existing diagnostic results; do not mark it complete.

**Deliverable:** one identified editor/decoder pair that recognizes an unchanged editor export, or a concise evidence-backed compatibility blocker.

### Step 3: Qualify matching behavior and hand off

**Files:** `tests/integration/test_oracle.py`, `tests/fixtures/oracle/` for compact generated traces, `docs/superpowers/evidence/task-3-native-oracle.md`; modify worker/adapter only if tests expose missing behavior.

- [ ] Run the existing semantic traces against the certified pair: A/B shared mask, hidden versus compared pixel change, exact unmasked C, single-shade change, repeated frame, unknown, reset, prior-match-dependent order, and advance-time calls. Production and observer renderer outputs must agree event by event.
- [ ] Verify all-hidden CRC zero, row-major raw shades, omitted mask bytes, reference-order changes, and the existing unequal-input CRC collision. Requalify diagnostic fixture derivatives against the certified format and label their provenance; use the untouched export for the primary acceptance trace.
- [ ] Save expected IDs, native result/flags/trigger/timing fields, renderer digests, CRCs, comparison-byte equality, and file hashes as golden evidence. Static advance-time coverage must not be described as certification of animation timing.
- [ ] Run `python -m pytest tests/integration/test_oracle.py -q -p no:cacheprovider`, then `python -m pytest -q -p no:cacheprovider` once. Native acceptance cases must run with verified binaries; skips do not certify them.
- [ ] Obtain one independent milestone review of the final diff and evidence. Fix only demonstrated correctness issues. Commit task-owned changes and update task status with proven behavior, unresolved obligations, and the exact next command for Task 4 (dump import).

## Completion gate

Task 3 is complete only when unchanged editor output recognizes correctly with the declared decoder, observer and production outputs agree, sequence/CRC/ordering cases pass, and worker isolation is verified. The existing nine diagnostic tests alone do not satisfy this gate. Task 4 dump import can proceed independently while a profile decision is pending.
