# Task 12 Bounded Jobs and Recovery Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task by task. Steps use checkbox (`- [ ]`) syntax for tracking. Leave changes uncommitted for the user's manual commit.

**Goal:** Run the fixed Twister analysis within a configurable budget, preserve the latest independently verified result, and resume compatible work without overstating export or coverage status.

**Architecture:** A small controller schedules the existing import, coverage, family, candidate, solver, and publication operations behind deadline-aware stage adapters. An append-only checkpoint journal records input identities, pending work, verified results, and measured stage costs; a new run validates those identities before reusing a checkpoint. The controller reports stop reason, recognition, coverage, optimality, and export separately.

**Tech Stack:** Python 3.11+, pytest, existing SQLite corpus and JSON manifests, monotonic clock, existing OR-Tools solver. No new dependency or GUI is required.

**Spec:** `DMD_Mask_Optimizer_Design_and_Implementation_Plan.md` §§3, 15–16; `docs/superpowers/plans/2026-11-18-dmd-mask-optimizer.md` Task 12; `AGENTS.md`.

## Global Constraints

- Default processing budget is 1,800 seconds, measured with a monotonic clock from initialization through export preparation. Record post-deadline flush time separately.
- The fixed `twst_405.txt` and immutable Task 9 corpus are the source for this build. Reuse that corpus capture, or create one worktree-local immutable import only if missing. Do not initiate a live intake, editor session, VPinMAME session, recorder, watcher, or interactive qualification for static analysis.
- A checkpoint identifies the ROM/profile, corpus revision, coverage/family/pool/solver algorithm versions and digests, and any native export digest. Reject or invalidate dependent work when any identity changes.
- A solver candidate is not a verified incumbent. Promote it only after independent verification of its declared scope; export status remains diagnostic-only unless native publication and replay have passed.
- Preserve prior published bundles and author edits. Write a new run directory, use atomic checkpoint publication, and never silently expand verified scope with late frames.
- Cancellation and deadline must stop scheduling new work. Bounded workers must terminate or report an explicit failure; flush duration and unfinished revisions remain visible.
- Task 12 provides a callable controller and progress events for Task 13. It does not build the desktop UI or claim complete ROM coverage.

## Review Focus

1. A frame arrives after the selected verified revision: retain it as pending, with the previous export revision unchanged (Task 2).
2. Cancellation or deadline lands during a blocking worker call: stop that worker within its assigned deadline and preserve the verified checkpoint (Task 2).
3. A checkpoint is truncated or its digest is altered: reject it and retain the last intact verified generation (Task 1).
4. A resumed run has a different profile, corpus, or algorithm digest: invalidate dependent hints and explain the mismatch (Task 3).
5. A diagnostic-only Task 11 bundle is present: report `export_status=diagnostic-only`; do not label it verified-editable (Task 2).

---

### Task 1: Define job state and durable checkpoints

**Files:** Create `src/dmd_optimizer/controller/model.py`, `src/dmd_optimizer/controller/checkpoint.py`, `src/dmd_optimizer/controller/__init__.py`, `tests/unit/test_controller_checkpoint.py`.

**Interfaces:** `RunRequest(rom_path: Path, dump_paths: tuple[Path, ...], output_dir: Path, budget_seconds: float = 1800, prior_run: Path | None = None)`; `RunResult(run_id, stop_reason, recognition_status, coverage_status, optimality_status, export_status, last_verified_revision, export_revision, pending_frames, checkpoint_digest, processing_seconds, flush_seconds, diagnostics)`; `save_checkpoint(run_dir: Path, state: JobState) -> str`; `load_checkpoint(run_dir: Path, expected: InputIdentity) -> JobState`. Define `InputIdentity` with exact profile, corpus revision, algorithms, and optional native artifact hashes. Use canonical JSON and SHA-256; preserve prior generations.

- [ ] **Step 1: Write failing tests** in `tests/unit/test_controller_checkpoint.py` for default 1,800-second budget, atomic save/read-back, generation fallback after a truncated newest file, checksum mismatch, and unchanged prior checkpoint after a failed write.
- [ ] **Step 2: Run** `uv run --group test pytest tests/unit/test_controller_checkpoint.py -q`; expect failures from missing controller/checkpoint interfaces.
- [ ] **Step 3: Implement** typed state, canonical hashing, durable generation files and a small atomic pointer. Reject malformed state and path escapes; checkpoint only immutable identities and references to files whose hashes were verified.
- [ ] **Step 4: Rerun** the focused tests; require all pass. Review the saved JSON for exact identity fields and absence of frame payloads.

### Task 2: Bound stages and preserve the verified result

**Files:** Create `src/dmd_optimizer/controller/run.py`, `src/dmd_optimizer/controller/stages.py`, `tests/integration/test_controller.py`.

**Interfaces:** `run_job(request: RunRequest, clock: Clock, stop: StopToken, *, stages: JobStages | None = None, progress: Callable[[ProgressEvent], None] | None = None) -> RunResult`. `Clock.monotonic() -> float`; `StopToken.stopped() -> bool`. `JobStages` exposes bounded `import_corpus`, `analyze`, `build_baseline`, `solve`, `verify`, and `publish` operations; each receives a monotonic deadline and returns a typed result. The production adapter calls existing Task 4–11 functions without inventing a native verification result.

- [ ] **Step 1: Write failing integration tests** with a fake monotonic clock and stage adapter. Assert `budget_seconds == 1800`, `export_revision == last_verified_revision`, and `pending_frames == 1` when a late frame appears. Exercise deadline at every stage, cancellation, worker death, zero budget, a diagnostic-only publisher result, and a run with no verified baseline.
- [ ] **Step 2: Run** `uv run --group test pytest tests/integration/test_controller.py -q`; expect failures from the missing scheduler.
- [ ] **Step 3: Implement** a monotonic deadline from initialization, bounded calls, progress events, and a measured reserve based on prior verification/export costs. Establish an exact baseline early where representable. Promote only a candidate that passed independent verification, publish only the last verified scope, and report pending revisions and final flush time separately. When native export is unavailable, retain the truthful diagnostic status.
- [ ] **Step 4: Rerun** focused tests; require each injected stop to leave an intact verified generation and independent status fields. Do not treat an ordinary Python test as native editor certification.

### Task 3: Resume with identity validation and immutable inputs

**Files:** Modify `src/dmd_optimizer/controller/run.py`, `src/dmd_optimizer/controller/checkpoint.py`; create `tests/integration/test_controller_resume.py`.

**Interfaces:** `run_job` accepts `RunRequest.prior_run`; `load_checkpoint` compares `InputIdentity` before supplying hints to `JobStages`. New budget starts at the new run's monotonic start, not at the old run's deadline.

- [ ] **Step 1: Write failing tests** for compatible resume, changed ROM/profile/corpus/algorithm identities, stale solver hint, changed native export digest, and preservation of an edited prior output directory. Assert each stale dependency is recomputed or marked pending with a specific reason.
- [ ] **Step 2: Run** `uv run --group test pytest tests/integration/test_controller_resume.py -q`; expect failures from absent resume validation.
- [ ] **Step 3: Implement** dependency-aware invalidation, new-run checkpoint generation, and reuse of compatible corpus/frontier/candidate/verified-solution hints. Open the fixed static corpus read-only and verify its revision and source digest before scheduling work. Do not launch an editor during resume qualification.
- [ ] **Step 4: Rerun** the resume tests; require no mutation of the prior run and exact invalidation diagnostics.

### Task 4: Qualify the fixed handoff and record evidence

**Files:** Create `scripts/run_bounded_job.py`, `docs/superpowers/evidence/task-12-bounded-jobs-recovery.md`; update `.superpowers/sdd/2026-11-27-task-12-bounded-jobs-recovery/progress.md`.

**Interfaces:** CLI accepts the fixed corpus/manifest paths, output root, optional prior-run directory, and `--budget-seconds`; emits a `RunResult` JSON with separate status fields. Reuse the immutable Task 9/10/11 handoff artifacts.

- [ ] **Step 1: Write a failing CLI integration test** for a short budget, a resume run, and deterministic fixed-input identity diagnostics. Assert the output points to the last verified generation or explicitly says none exists.
- [ ] **Step 2: Run** the CLI test; expect failure from the missing entry point.
- [ ] **Step 3: Implement** the thin CLI and run one short fixed-input qualification using only corpus/manifests. Record input/checkpoint hashes, stage durations, stop reason, pending frames, publication status, and whether native eligibility remains unresolved. Abort a stage at its deadline; do not run a long editor or native capture process for this qualification.
- [ ] **Step 4: Run** `uv run --group test pytest tests/unit/test_controller_checkpoint.py tests/integration/test_controller.py tests/integration/test_controller_resume.py tests/integration/test_export.py -q` and `git diff --check`; require zero failures. Run the project suite once if the focused checks pass. Save evidence and progress locally; leave all files uncommitted for the user's manual commit.

## Completion

Task 12 is complete when the controller enforces the default and custom budgets across stages, returns the last independently verified scope or honest diagnostics, survives cancellation/deadline/worker failure with a recoverable checkpoint, resumes only compatible work under a new budget, and reports processing time, flush time, pending revisions, and export/coverage/optimality status separately. A live 30-minute packaged application run belongs to Task 14.
