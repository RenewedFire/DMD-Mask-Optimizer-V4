# DMD Mask Optimizer Implementation Plan

> **For agentic workers:** Use superpowers:subagent-driven-development or superpowers:executing-plans to implement this plan task by task. Check each box only after collecting its evidence.

**Goal:** Give a Windows colorization author an editable original-ColorizingDMD project whose comparison masks recognize a documented set of ROM outputs while preserving source pixels and occurrences.

**Architecture:** A desktop controller drives a persisted Python engine. Isolated native workers capture PinMAME identification frames and exercise the pinned legacy editor and matcher. Every published assignment refers to an immutable corpus revision and an exported artifact that passed verification.

**Tech stack:** Python, NumPy, SQLite, packed bitsets, OR-Tools CP-SAT, PySide6, C++ and Windows x64. Record exact build and package versions when the corresponding compatibility tests pass.

**Spec:** [Approved design, revision 2.1](../../../DMD_Mask_Optimizer_Design_and_Implementation_Plan.md). Section 22 fixes the first compatibility profile. All tasks below are prospective.

## Global constraints

- Start with Twister 4.05, 128×32, four native shades, original SerumColor ColorizingDMD and stable PinMAME 3.6. Resolve exact commits, compiler flags, architectures and binary hashes during compatibility work. Allow an out-of-process bridge matching the editor's own bitness.
- Accept a ROM selected at runtime. Bind support to tested revision, driver, geometry and delivery semantics. Keep the supplied ROM and captures local. Use generated fixtures for distributable tests.
- Use normal comparison, ignore bit one internally, and strict discrimination against every covered incompatible family. Preserve moving graphics, fixed text and brightness differences outside established fields. Keep separate exact references for uncertain and observed-only cases.
- Minimize distinct active custom bitmaps, then redundant references, then measured runtime cost. Unmasked references cost zero. Freeze established families and their domains before each solve.
- Budget 30 minutes by default, configurable from Start through export preparation. Preserve the last verified checkpoint and report final flush time separately. The normal workflow requires no manual grouping approval.
- Report stop reason, recognition, coverage, optimality and export as independent fields. The target includes every supported language and setting. A provisional export identifies its tested scope, pending inputs and outstanding proof obligations.

## Review focus

1. A plausible dump with two malformed records whose row counts average 32 must fail per record (Task 4).
2. A repeated frame after a reset may select a different reference. Preserve sequence, reset boundaries and native clock calls (Tasks 3–5).
3. A shared mask can pass pairwise tests and still erase a distinction when three families share it. Check each materialized union (Task 9).
4. A reference omitted from a partial project can still arrive at playback. Check omitted known negatives for accidental matches (Task 11).
5. An author may edit yesterday's project before resuming today. Publish the new verified revision separately and preserve those edits (Tasks 11–12).

---

## Working structure and test convention

The starting folder contains the approved design and the two fixtures. Paths below are proposed files. In the task table, Python module paths beginning with `@` are relative to `src/dmd_optimizer/`. Each numbered task owns its listed files and its matching test file. Test directories distinguish generated unit cases, native integration, local fixtures and packaged acceptance. Use a pytest fixture named `case` scoped to each module to build the named scenario in a temporary directory. Assertions below specify its observable results.

| Tasks | Files and responsibilities |
| --- | --- |
| 1–3 | `profiles/twst_405.json`, `scripts/lock_profile.py`, `pyproject.toml` for provenance and testing. `native/CMakeLists.txt`, `native/editor_bridge.cpp`, `@adapters/editor.py` for editable projects. `native/serum_worker.cpp`, `@verify/oracle.py`, `schemas/worker-v1.json` for native replay. |
| 4–6 | `@capture/text_dump.py` for record parsing. `@corpus/store.py`, `schemas/corpus-v1.sql` for frames, occurrences and revisions. `native/pinmame_worker.cpp`, `@rom/audit.py`, `@capture/live.py` for ROM identity and raw delivery. |
| 7–10 | `@explore/frontier.py` for configurations and input scripts. `@families/infer.py` for evidence-backed domains. `@masks/candidates.py` for candidate validity. `@solve/cover.py` for mask assignment. |
| 11–14 | `@verify/exported.py`, `@adapters/bundle.py`, `@report.py` for verified outputs. `@controller.py` for jobs and recovery. `@ui/main.py` for the desktop entry point. `packaging/windows.spec`, `scripts/qualify.py` for distribution and release measurements. |

Use the task order below as the default. Tasks 2 and 4 can proceed independently once the fixture identity is locked. Native certification requires Tasks 2, 3 and 6. Tasks 7–14 consume the resulting profile. Keep the native smoke tests runnable by themselves throughout development.

**Evidence conventions.** Run commands in PowerShell from the workspace root in the implementation environment. Write generated evidence beneath `artifacts/<run-id>/`. Record command, exit status, input hashes and output hashes alongside each result. For each task run its test once before and once after implementation. A missing fixture or skipped native test cannot certify a release. In a Git checkout commit only the task-owned source, synthetic tests and permitted metadata after green. In this standalone folder use a task completion record until repository history is available.

### Task 1 — Lock the reproducible fixture and build inputs

**Files:** Use the Task 1 area of the working structure above. Create `tests/integration/test_profile.py`.

**Interface:** `lock_profile(rom: Path, dump: Path, toolchain: Path) -> Profile`

**Inputs:** Both local files and the original sources listed in design §3.

- [ ] Write `test_profile` and its fixtures. Start with `assert case.rom_sha256 == '7419195a51f1295e9f928e0105326cba3c4e32b9b2d3b59c004f773d132707a3' and case.dump_sha256 == 'f711aec5d42fdc423ca02bfd2c8f05c158afaee27a97acdbf59d532b81095b11'.lower()`. Add the failure cases described below.
- [ ] Run `python -m pytest tests/integration/test_profile.py -q` and confirm a failure attributable to the missing behavior.
- [ ] Implement the interface. Compute byte digests and member inventory. Resolve the original editor and bundled decoder to one full commit and stable PinMAME 3.6 to one full commit. Build or acquire matching binaries, record digests, flags, build commands, toolchain and dependency lock. Fail with the component name on a changed binary. Ignore local inputs and build artifacts in version control.
- [ ] Rerun `python -m pytest tests/integration/test_profile.py -q`. Require all assertions to pass. A clean Windows environment can reproduce the profile or name a specific missing input. Record the profile digest and synthetic/local test commands.
- [ ] Record the evidence and checkpoint the task under the working convention above.

### Task 2 — Prove the original editor round trip

**Files:** Use the Task 2 area of the working structure above. Create `tests/integration/test_editor_roundtrip.py`.

**Interface:** `write_project(folder: Path, refs: Sequence[Reference], profile: Profile) -> ProjectFiles`

**Inputs:** Task 1 profile. Reference carries stable ID, native pixels, optional ignore bitmap and shape=false.

- [ ] Write `test_editor_roundtrip` and its fixtures. Start with `assert case.reopened.source_pixels == case.input_pixels and case.reopened.custom_mask_count == 1`. Add the failure cases described below.
- [ ] Run `python -m pytest tests/integration/test_editor_roundtrip.py -q` and confirm a failure attributable to the missing behavior.
- [ ] Implement the interface. Use the actual original editor model/serializer through a small bridge. Generate three synthetic refs, two sharing a bitmap and one unmasked. Open in the pinned editor, save to a fresh folder, reopen and export the runtime file. Record actual companion names, headers, field widths, endianness, defaults and slot limits. Observe sentinel 255 and 64-slot capacity on this build. Check mask assignment, native grayscale, source order and retained hidden pixels.
- [ ] Rerun `python -m pytest tests/integration/test_editor_roundtrip.py -q`. Require all assertions to pass. A human can open the saved editable project and the native loader accepts the runtime export. Keep the small generated golden package and binary fingerprints. If a bridge is infeasible, require the same editor golden comparison for a standalone writer.
- [ ] Record the evidence and checkpoint the task under the working convention above.

### Task 3 — Establish the native matching oracle

**Files:** Use the Task 3 area of the working structure above. Create `tests/integration/test_oracle.py`.

**Interface:** `replay(project: ProjectFiles, events: Iterable[ReplayEvent], profile: Profile) -> Iterator[Match]`

**Inputs:** Task 2 runtime export. ReplayEvent is reset, advance-time or frame with pixels. Match records stable reference or unknown plus observable events.

- [ ] Write `test_oracle` and its fixtures. Start with `assert case.native_ids == case.expected_ids and case.instrumented_outputs == case.production_outputs`. Add the failure cases described below.
- [ ] Run `python -m pytest tests/integration/test_oracle.py -q` and confirm a failure attributable to the missing behavior.
- [ ] Implement the interface. Use one native instance per process. Bound request length by geometry, validate protocol version, and add timeout, reset, exit and shutdown paths. Use distinguishable test colors and native reference instrumentation. Compare masked, unmasked, all-hidden, single-brightness-change, repeated and unknown frames, from reset and different previous matches. Derive CRC traversal, omitted bytes, raw shade mapping and lookup order from the selected implementation. Save golden CRCs and sequences.
- [ ] Rerun `python -m pytest tests/integration/test_oracle.py -q`. Require all assertions to pass. Capture a known CRC collision with unequal inputs, distinguish it from identical compared bytes, and demonstrate lookup parity after changing reference order. A timeout terminates only the affected worker.
- [ ] Record the evidence and checkpoint the task under the working convention above.

### Task 4 — Import and characterize every dump record

**Files:** Use the Task 4 area of the working structure above. Create `tests/local/test_twister_dump.py`.

**Interface:** `read_dump(path: Path, profile: Profile) -> Iterator[OccurrenceInput]`

**Inputs:** Task 1 dump. OccurrenceInput includes session, index, original tick, duration status, offset and native pixels.

- [ ] Write `test_twister_dump` and its fixtures. Start with `assert case.frames == 14443 and case.bad_records == 0 and case.shades == {0,1,2,3}`. Add the failure cases described below.
- [ ] Run `python -m pytest tests/local/test_twister_dump.py -q` and confirm a failure attributable to the missing behavior.
- [ ] Implement the interface. Stream timestamp headers and exactly 32 rows of exactly 128 symbols per frame. Require a valid delimiter and record boundary, retain offsets, accept verified line endings and reject incomplete EOF. Test paired 31/33-row records, overflow, invalid symbol and timestamps with reset/wrap/ambiguous ordering. Preserve unknown final duration. Prove tick units against producer evidence or controlled timing before timed replay. Add generated malformed cases under tests/unit/test_text_dump.py.
- [ ] Rerun `python -m pytest tests/local/test_twister_dump.py -q`. Require all assertions to pass. Report first and last ticks 0x00088B41 and 0x00227C3F, exact per-record sizes and diagnostic offsets. Optional diagnostic salvage explicitly marks incompleteness. Additional raw/ZIP dump grammars require separate fixtures.
- [ ] Record the evidence and checkpoint the task under the working convention above.

### Task 5 — Persist immutable corpus revisions

**Files:** Use the Task 5 area of the working structure above. Create `tests/unit/test_corpus.py`.

**Interface:** `append_capture(project: Path, source: Capture, occurrences: Iterable[OccurrenceInput]) -> Revision`

**Inputs:** Task 4 iterator. Capture includes provenance, complete flag, producer and configuration. Revision carries digest and counts.

- [ ] Write `test_corpus` and its fixtures. Start with `assert case.unique_frames == 2 and case.occurrence_ids == ['A','A','B'] and case.previous_revision_readable`. Add the failure cases described below.
- [ ] Run `python -m pytest tests/unit/test_corpus.py -q` and confirm a failure attributable to the missing behavior.
- [ ] Implement the interface. Hash geometry, encoding, normalization and bytes, comparing bytes on a digest hit. Write and checksum chunks before committing SQLite references. Preserve capture source, offsets, absolute order and timestamps. Version family inputs, constraints and downstream artifacts by digest. Inject interruption on each side of commit and exclude orphan chunks on restart.
- [ ] Rerun `python -m pytest tests/unit/test_corpus.py -q`. Require all assertions to pass. Reimport keeps stable frame IDs. Deliberate digest collision preserves both images. A new capture creates a new revision and earlier verification remains reproducible.
- [ ] Record the evidence and checkpoint the task under the working convention above.

### Task 6 — Audit the selected ROM and prove capture parity

**Files:** Use the Task 6 area of the working structure above. Create `tests/local/test_twister_capture.py`.

**Interface:** `audit_rom(path: Path, profile: Profile) -> AuditResult and capture(session: CaptureRequest) -> Iterator[OccurrenceInput]`

**Inputs:** Tasks 1, 3–5. CaptureRequest carries audited ROM, settings, input schedule and stop limit.

- [ ] Write `test_twister_capture` and its fixtures. Start with `assert case.audited_revision == 'twst_405' and case.capture_stream == case.identification_stream and len(case.capture_stream) > 0`. Add the failure cases described below.
- [ ] Run `python -m pytest tests/local/test_twister_capture.py -q` and confirm a failure attributable to the missing behavior.
- [ ] Implement the interface. Audit member content, parent dependencies and driver metadata with pinned PinMAME. Select by identity even if archive is renamed. Run a controlled boot and input sequence. Tap identification delivery and compare it occurrence by occurrence with the bytes offered to the runtime consumer in the same run, including repeated calls, geometry, shade values and timing. Comparing two different play sessions is insufficient. Reject luminance-only output and unsupported display semantics.
- [ ] Rerun `python -m pytest tests/local/test_twister_capture.py -q`. Require all assertions to pass. Archive independent traces and first divergence on error. Missing parent/member and an unsupported ROM get actionable diagnostics. Mark only passing driver/revision/delivery combinations as supported.
- [ ] Record the evidence and checkpoint the task under the working convention above.

### Task 7 — Explore configurations and retain the frontier

**Files:** Use the Task 7 area of the working structure above. Create `tests/integration/test_exploration.py`.

**Interface:** `explore(request: CaptureRequest, frontier: Frontier, stop: StopToken) -> ExplorationResult`

**Inputs:** Task 6 capture and Task 5 append_capture. Frontier records initial/NVRAM state, configuration, scripted inputs and next unexplored actions.

- [ ] Write `test_exploration` and its fixtures. Start with `assert case.resumed_action_ids == case.uninterrupted_action_ids and case.coverage.total_reachable is None`. Add the failure cases described below.
- [ ] Run `python -m pytest tests/integration/test_exploration.py -q` and confirm a failure attributable to the missing behavior.
- [ ] Implement the interface. Enumerate verified language/settings values and valid initial states. Use driver scripts for boot, attract, service, play, scores, multiplayer, mode transitions and initials. Track actual exercised states, gaps, unsupported controls and novelty. Persist deterministic restart/replay recipes when full emulator snapshots are unavailable. Reserve independent capture sessions for validation.
- [ ] Rerun `python -m pytest tests/integration/test_exploration.py -q`. Require all assertions to pass. A short run and resume advance the frontier and attach configuration evidence. Unknown settings, interrupted paths and saturation yield provisional coverage. Test ROM-only execution with no supplied dump.
- [ ] Record the evidence and checkpoint the task under the working convention above.

### Task 8 — Freeze independently supported recognition families

**Files:** Use the Task 8 area of the working structure above. Create `tests/unit/test_families.py`.

**Interface:** `infer(revision: Revision, evidence: Sequence[FieldEvidence]) -> FamilySet`

**Inputs:** Task 5 pixels and Task 7 training sessions. FieldEvidence specifies value source, ranges, glyphs, positions and correlations.

- [ ] Write `test_families` and its fixtures. Start with `assert case.score_family.covers(case.held_out_value) and case.moving_ref != case.static_ref and case.uncertain_is_singleton`. Add the failure cases described below.
- [ ] Run `python -m pytest tests/unit/test_families.py -q` and confirm a failure attributable to the missing behavior.
- [ ] Implement the interface. Segment exact layout/animation states. Verify rendering provenance and modeled variation in width, alignment, clipping, punctuation, names and linked fields. Compute required ignored pixels, must-compare pixels and the exact domain for each supported family. Give unsupported variation separate exact references and a reason. Keep identical visual payloads with conflicting contextual expectations traceable.
- [ ] Rerun `python -m pytest tests/unit/test_families.py -q`. Require all assertions to pass. Independently labeled digits, static labels, sliding text, animation and intensity tests distinguish false merges from missed generalizations. Holdout inputs never fit the model. Freeze and hash each family specification.
- [ ] Record the evidence and checkpoint the task under the working convention above.

### Task 9 — Validate reusable comparison masks

**Files:** Use the Task 9 area of the working structure above. Create `tests/unit/test_candidates.py`.

**Interface:** `generate(families: FamilySet, revision: Revision, profile: Profile) -> OptionPool`

**Inputs:** Task 8 domains and Task 3 native oracle. OptionPool records verified options per family and failure witnesses.

- [ ] Write `test_candidates` and its fixtures. Start with `assert case.shared_pair_valid and not case.three_way_union_valid and case.hash_collision_rejected`. Add the failure cases described below.
- [ ] Run `python -m pytest tests/unit/test_candidates.py -q` and confirm a failure attributable to the missing behavior.
- [ ] Implement the interface. Start with unmasked rules, existing bitmaps and each family's minimum ignore set. Materialize promising unions and preserve stable distinguishing pixels. Check invariance for every positive value in the claimed domain and exact native CRC against every incompatible covered input across all masks. Require a complete domain check for a modeled claim. On incomplete checks reduce the claimed scope to verified observations and retain exact fallbacks. Cache by revision, domain, mask and profile.
- [ ] Rerun `python -m pytest tests/unit/test_candidates.py -q`. Require all assertions to pass. Use synthetic higher-order conflicts, equal compared bytes, distinct bytes with equal CRC, all-hidden masks and shape-disabled brightness negatives. Store a concrete witness for each rejection.
- [ ] Record the evidence and checkpoint the task under the working convention above.

### Task 10 — Select and bound the best feasible assignment

**Files:** Use the Task 10 area of the working structure above. Create `tests/unit/test_solver.py`.

**Interface:** `solve(pool: OptionPool, profile: Profile, stop: StopToken) -> SolveResult`

**Inputs:** Task 9 verified options for a frozen scope. SolveResult includes assignment, mask count, status, bound, scope and model digest.

- [ ] Write `test_solver` and its fixtures. Start with `assert case.selected_mask_count == case.brute_force_minimum == 2 and case.unmasked_cost == 0`. Add the failure cases described below.
- [ ] Run `python -m pytest tests/unit/test_solver.py -q` and confirm a failure attributable to the missing behavior.
- [ ] Implement the interface. Implement deterministic greedy incumbent then CP-SAT shared-mask activation and one option per family. Enforce the profile cap and distinct bitmap cost. Optimize secondary objectives only with the primary value fixed, preserving established family domains. Separate no feasible option, solver unknown, timeout and proof of pool infeasibility. Save candidate solutions for artifact verification before promoting them.
- [ ] Rerun `python -m pytest tests/unit/test_solver.py -q`. Require all assertions to pass. On tiny synthetic geometries enumerate assignments and all bitmaps independently. Demonstrate at least one useful shared mask, a zero-saving case, and a restricted pool whose optimum exceeds the unrestricted minimum. Report lower bounds only with matching scope.
- [ ] Record the evidence and checkpoint the task under the working convention above.

### Task 11 — Publish a verified editable bundle

**Files:** Use the Task 11 area of the working structure above. Create `tests/integration/test_export.py`.

**Interface:** `publish(result: SolveResult, revision: Revision, folder: Path) -> ExportRecord`

**Inputs:** Tasks 2–3 staged-editor/runtime verification and Tasks 5–10 immutable inputs, options and coverage. The bridge supplies only the fixed dump's native path/digest/count to the editor; it never transports derived frame data.

- [ ] Write `test_export` and its fixtures. Start with `assert case.wrong_family_matches == 0 and case.mapped_occurrences == case.input_occurrences and case.author_edit_preserved`. Add the failure cases described below.
- [ ] Run `python -m pytest tests/integration/test_export.py -q` and confirm a failure attributable to the missing behavior.
- [ ] Implement the interface. Compile final slots/indices in a sibling staging directory. Use the staged editor's native TXT import with the original fixed dump path, then reopen/save/export, reload final runtime bytes and replay ordered sessions, repeats, held-out cases, unknowns and domain variants. Check stable IDs after reordering. Write masks.json, mask previews, raw references and previews, frame_mapping.csv, optimization.json, coverage.json and report.html. Include all input occurrences with assignment or omission reason. Hash files, reconcile mapping and publish atomically under a fresh run directory. Do not send reconstructed frames, masks, or timestamps through the bridge.
- [ ] Rerun `python -m pytest tests/integration/test_export.py -q`. Require all assertions to pass. Try full scope, then a valid strict subset with explicit omissions checked against retained rules. Otherwise publish diagnostic/source outputs. Test disk or reopen failure, known negatives outside the subset, final artifact digest, equivalent repeated exports and preservation of existing author edits.
- [ ] Record the evidence and checkpoint the task under the working convention above.

### Task 12 — Bound jobs and recover verified work

**Files:** Use the Task 12 area of the working structure above. Create `tests/integration/test_controller.py`.

**Interface:** `run_job(request: RunRequest, clock: Clock, stop: StopToken) -> RunResult`

**Inputs:** Tasks 4–11. RunRequest holds ROM, optional dumps, output directory, prior run and budget. RunResult includes independent status fields, checkpoint digest and pending revisions.

- [ ] Write `test_controller` and its fixtures. Start with `assert case.budget_seconds == 1800 and case.export_revision == case.last_verified_revision and case.pending_frames == 1`. Add the failure cases described below.
- [ ] Run `python -m pytest tests/integration/test_controller.py -q` and confirm a failure attributable to the missing behavior.
- [ ] Implement the interface. Use a monotonic end time and bounded worker operations from initialization onward. Build an exact baseline for representable scope early and promote only independently verified artifacts. Reserve measured time for verification/export, stream checkpoint progress and adapt exploration/solver allocation. Inject cancel, worker death and deadline at each stage. Resume in a new budget after checking profile, corpus and algorithm digests.
- [ ] Rerun `python -m pytest tests/integration/test_controller.py -q`. Require all assertions to pass. A late frame cannot silently expand the verified scope. Simulated deadlines stop scheduling and report flush time. With no verified incumbent return a verified baseline if available, otherwise diagnostics. Resume accepts valid hints and invalidates stale work.
- [ ] Record the evidence and checkpoint the task under the working convention above.

### Task 13 — Deliver the desktop authoring workflow

**Files:** Use the Task 13 area of the working structure above. Create `tests/integration/test_desktop.py`.

**Interface:** `launch_desktop(controller: JobController) -> int`

**Inputs:** Task 12 run_job exposed through a background JobController with start, cancel, resume and progress signals.

- [ ] Write `test_desktop` and its fixtures. Start with `assert case.ui_responsive and case.run_without_manual_grouping and case.opened_project == case.exported_project`. Add the failure cases described below.
- [ ] Run `python -m pytest tests/integration/test_desktop.py -q` and confirm a failure attributable to the missing behavior.
- [ ] Implement the interface. Build Load ROM, optional Add Dumps, output and budget controls. Display dependency diagnostics, geometry, elapsed/remaining time, discovered frames, tested settings and verified mask count. Show integer-scale native shade previews, mask overlays, pending frames and failed witnesses. Open the exact published project, separate exports and report. Wire cancel and resume to persisted job IDs.
- [ ] Rerun `python -m pytest tests/integration/test_desktop.py -q`. Require all assertions to pass. Drive the real window on Windows with generated inputs, then exercise the legal Twister fixture. Check the ROM-only path, a cancelled run and paths containing spaces. Packaging uses this same entry point.
- [ ] Record the evidence and checkpoint the task under the working convention above.

### Task 14 — Qualify and package the Twister profile

**Files:** Use the Task 14 area of the working structure above. Create `tests/acceptance/test_release.py`.

**Interface:** `qualify(build: Path, fixtures: Path, output: Path) -> QualificationReport`

**Inputs:** Tasks 1–13 and a clean Windows x64 test environment. QualificationReport links toolchain, fixture, package and run digests.

- [ ] Write `test_release` and its fixtures. Start with `assert case.wrong_family_matches == 0 and case.packaged_ui_smoke_passed and case.bundle_reconciled`. Add the failure cases described below.
- [ ] Run `python -m pytest tests/acceptance/test_release.py -q` and confirm a failure attributable to the missing behavior.
- [ ] Implement the interface. Freeze the tested dependencies and package the desktop executable with the correct native workers and required runtime files. Run a genuine 30-minute Twister job on the 8-core/16 GB target, plus shortened deadline, cancellation, resume, missing dependencies and unsupported geometry cases. Use a generated scale corpus of one million occurrences, up to 100,000 unique 128×32 inputs and 1,000 established families. Stream frames and cap worker/cache memory.
- [ ] Rerun `python -m pytest tests/acceptance/test_release.py -q`. Require all assertions to pass. Archive elapsed time and cleanup, peak memory, latency distribution against measured delivery cadence, references, masks, uncertainty and proof scope. Reopen the delivered project independently on a clean machine. Ship only passing profiles. Record scale shortfalls and actual supported capacity before making a performance claim.
- [ ] Record the evidence and checkpoint the task under the working convention above.

## Milestone sign-off

| Design milestone | Tasks | Evidence to inspect |
| --- | --- | --- |
| M0 compatibility | 1–3, 6 | Content-addressed profile, native capture comparison, tiny editable project and replay transcript |
| M1 inputs and shell | 4–6, 13 | Full dump parse, lossless occurrences, ROM audit and chooser |
| M2 runtime oracle | 3, 9, 11 | Golden CRCs, expected IDs, ordered native replay and final-slot validation |
| M3 exploration | 6–7 | Recorded switches/settings, source occurrences, saved frontier and resume transcript |
| M4 automatic grouping | 8 | Independent labels, domain evidence and separate uncertain references |
| M5 optimization | 9–10 | Negative witnesses, enumeration checks, scoped bounds and time-limited incumbent |
| M6 outputs | 2, 11 | Editable project that reopens, export digests and per-occurrence reconciliation |
| M7 budget and recovery | 5, 12–13 | Deadline/cancel/crash evidence in each phase and recoverable UI result |
| M8 Windows qualification | 14 | Packaged workflow and measurements for the certified fixture on named hardware |

## Subsequent profiles and M9

For each additional revision, driver or geometry, repeat Tasks 1–6 and 14 using independent local fixtures. Record comparison resolution, shade mapping, polarity, timing and an editor round trip for that profile. Expand the published support matrix one passing profile at a time. Twister is the MVP anchor. The broader release criterion in design §17 requires multiple tested driver/geometry fixtures.

Direct all-mask synthesis and exhaustive ROM coverage are subsequent deliverables. For synthesis, extend Task 10 with pixel/slot variables, lazy negative constraints and exact CRC counterexample checks. Accept an all-mask optimum only when a valid lower bound meets a verified upper bound on the identical frozen domain and strict policy. For coverage, extend Task 7 with a complete reachable-state frontier or a sound renderer abstraction over the declared configuration, input and NVRAM domains. Validate closure with a complete checker and archive its evidence. Until then, report the known counts, unknown denominator and remaining obligations.

## Release decision

Run `python -m pytest tests/unit tests/integration tests/local tests/acceptance -q` on the configured qualification machine. Inspect local/native test collection, run the packaged application through its normal desktop path and retain the qualification report. A clean Python suite alone cannot establish native or packaged compatibility. A correct provisional Twister project is an acceptable budget outcome. A mismatch in the declared verified scope blocks publication of that assignment.

