# Task 13 Desktop Authoring Workflow Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task by task. Steps use checkbox (`- [ ]`) syntax for tracking. Save evidence locally. The user will sync the local commit to GitHub.

**Goal:** Give a Windows user one responsive desktop window to select a ROM and optional dumps, run the bounded optimizer, inspect progress and results, cancel or resume, and open the exact published outputs.

**Architecture:** A PySide6 window owns input and result views; a background `JobController` adapts Task 12's `run_job` to Qt signals. A pure view model converts controller events and result records into display state so status and link behavior can be tested without starting real applications. The production runner reads the immutable fixed corpus for this Twister build and reports unavailable capabilities honestly.

**Tech Stack:** Python 3.11+, PySide6, pytest with a Qt test helper, existing Task 12 controller and manifest formats. The executable package is Task 14.

**Spec:** `DMD_Mask_Optimizer_Design_and_Implementation_Plan.md` §§3, 15–16; `docs/superpowers/plans/2026-11-18-dmd-mask-optimizer.md` Task 13; `docs/superpowers/plans/2026-11-27-task-12-bounded-jobs-recovery.md`; `AGENTS.md`.

## Global Constraints

- Default run budget is 1,800 seconds; display elapsed and remaining processing time and post-deadline flush time separately.
- The fixed `twst_405.txt` and immutable corpus capture are canonical for this build. Do not create an interactive qualification, live recorder, folder watcher, VPinMAME session, or ColorizingDMD session to analyze it. Use direct corpus analysis and generated UI fixtures.
- The editor bridge is not a production data transport. Show an editable project action only when a verified published project path exists. Diagnostic-only output opens its report and companion files without an editable-project claim.
- Use the existing tested ROM/profile scope. An unsupported ROM or missing dependency receives a clear diagnostic; the UI must not silently label it supported.
- Do not make family grouping or approval a required step. Preserve all prior outputs and author edits; resume creates a new run with compatible checkpoint validation.
- No UI work may block the Qt event loop. Cancel must signal the controller promptly; the worker retains the latest verified checkpoint and finishes within its bounded operation contract.
- Work locally in the isolated development worktree; preserve the main project and existing colorization projects. Synchronize the plan/evidence to the main docs folder when requested.

## Review Focus

1. An output is diagnostic-only: disable “Open editable project,” but allow the report and companion folder to open (Task 3).
2. A job is running when the user presses Cancel or closes the window: request cancellation and show the final checkpoint status without freezing or abandoning a live worker (Tasks 1–2).
3. A prior run has mismatched ROM/profile/corpus/algorithm identity: show the Task 12 resume diagnostic and start a fresh run without mutating the old output (Task 2).
4. A path contains spaces, is missing, or refers to an unsupported ROM: validate it before Start and give an actionable message (Task 2).
5. A long preview or status stream arrives rapidly: retain integer pixel scaling and keep the window responsive by bounded event batching (Task 3).

---

### Task 1: Background job adapter and progress contract

**Files:** Create `src/dmd_optimizer/ui/job_controller.py`, `src/dmd_optimizer/ui/__init__.py`, `tests/unit/test_job_controller.py`; modify `src/dmd_optimizer/controller/run.py` only if a richer progress event is required by this adapter.

**Interfaces:** `JobController.start(request: RunRequest) -> str`, `cancel() -> None`, `resume(prior_run: Path, request: RunRequest) -> str`; Qt signals `progress(ProgressView)`, `finished(RunResult)`, `failed(str)`. `ProgressView` carries stage, elapsed/remaining seconds, discovered frames, tested settings, verified masks, pending frames, and current status fields. One worker may run at a time. The underlying runner remains `run_job(request, clock, stop, *, stages, progress) -> RunResult`.

- [ ] **Step 1: Write failing tests** for start → progress → finish, Cancel during an active stage, no second simultaneous run, and a worker exception converted into a visible failure. Assert the main event loop processes a timer while a fake slow job runs.
- [ ] **Step 2: Run** `uv run --group test pytest tests/unit/test_job_controller.py -q`; expect missing adapter behavior.
- [ ] **Step 3: Implement** a `QObject` worker on a `QThread` with a thread-safe stop token. Queue Qt signals to the window thread and detach cleanly only after the worker exits. If Task 12's string-only progress callback lacks counts, add an optional typed event without breaking its existing tests; derive display counts from verified state, never guesses.
- [ ] **Step 4: Rerun** focused tests; require event-loop responsiveness and a clean worker shutdown.

### Task 2: Input workflow and resume

**Files:** Create `src/dmd_optimizer/ui/main.py`, `src/dmd_optimizer/ui/inputs.py`, `tests/integration/test_desktop.py`.

**Interfaces:** `launch_desktop(controller: JobController | None = None) -> int`; `validate_inputs(rom: Path, dumps: tuple[Path, ...], output: Path, budget_seconds: float, prior_run: Path | None) -> RunRequest`. `MainWindow` exposes Load ROM, optional Add Dumps, output folder, run limit, Start, Cancel, and Resume controls.

- [ ] **Step 1: Write failing tests** for 1,800-second default, supported Twister ZIP selection, multiple optional TXT dumps, ROM-only path, paths with spaces, invalid/missing file, unsupported profile, Start/Cancel/Resume wiring, and no manual grouping prompt. Use generated files and a fake controller.
- [ ] **Step 2: Run** `uv run --group test pytest tests/integration/test_desktop.py -q`; expect missing UI behavior.
- [ ] **Step 3: Implement** the input form and validation against the pinned profile/ROM audit. For this fixed build, the immutable corpus capture is used for analysis even when the UI displays the canonical dump path; additional dumps require an explicitly supported import revision and cannot silently alter this run. Route resume through Task 12 identity checks and show a mismatch as a fresh-run diagnostic.
- [ ] **Step 4: Rerun** focused tests; require responsiveness and correct request paths. Do not launch ColorizingDMD or VPinMAME during this qualification.

### Task 3: Results, previews, and exact output actions

**Files:** Create `src/dmd_optimizer/ui/results.py`, `src/dmd_optimizer/ui/preview.py`; extend `src/dmd_optimizer/ui/main.py` and `tests/integration/test_desktop.py`.

**Interfaces:** `ResultView.from_run(result: RunResult, manifest: Mapping[str, object] | None) -> ResultView`; `render_frame(native_pixels: bytes, width: int, height: int, scale: int, ignore_bitmap: bytes | None = None) -> QImage`. Result paths resolve from the verified manifest, not from a guessed output filename.

- [ ] **Step 1: Write failing tests** for separate stop/recognition/coverage/optimality/export labels; elapsed, remaining and flush display; pending frames and failed witnesses; four-shade integer-scale preview and optional mask overlay; safe opening of exact published project/report/folder; diagnostic-only and missing-path actions disabled appropriately; rapid progress updates.
- [ ] **Step 2: Run** `uv run --group test pytest tests/integration/test_desktop.py -q`; expect missing result/preview behavior.
- [ ] **Step 3: Implement** result panels, integer-scale pixel rendering, mask overlay, bounded update coalescing, and exact output actions. Require a verified project path plus file existence before enabling editable-project launch. Keep report/folder opening separate from any editor session used for analysis.
- [ ] **Step 4: Rerun** focused tests; verify displayed counts against the immutable Task 9/10/11 manifests and diagnostic-only status.

### Task 4: Desktop entry point and Windows qualification

**Files:** Create `scripts/launch_desktop.py`, `docs/superpowers/evidence/task-13-desktop-authoring-workflow.md`; extend `tests/integration/test_desktop.py`.

**Interfaces:** `python scripts/launch_desktop.py` starts the same `launch_desktop` entry point that Task 14 packages. `--check` validates dependencies and prints a JSON readiness report without opening a window.

- [ ] **Step 1: Write failing entry-point tests** for `--check`, missing PySide6, missing fixed corpus, supported profile, and the normal window startup with generated fixtures. Assert no editor/PinMAME process is required for these checks.
- [ ] **Step 2: Run** `uv run --group test pytest tests/integration/test_desktop.py -q`; expect the new entry-point checks to fail.
- [ ] **Step 3: Implement** the thin launcher and run bounded Windows window tests with generated inputs plus a read-only fixed Twister artifact display. Record the exact dependency checks, window responsiveness, cancel/resume result, output action targets, and any unsupported capability. Keep real 30-minute and packaged acceptance runs for Task 14.
- [ ] **Step 4: Run** focused desktop/controller tests, then `uv run --group test pytest -q` and `git diff --check`; require zero failures. Save local evidence and the Task 13 progress ledger. Review the whole Task 13 diff before declaring completion.

## Completion

Task 13 is complete when a Windows user can start, cancel and resume a bounded run from the desktop window without a manual grouping step; the window remains responsive; every displayed status and count is backed by controller state; and output actions open only the exact verified paths. The fixed Twister UI qualification must use its immutable corpus. Native project publication remains diagnostic-only until a separately verified publisher produces an editable artifact.
