# Task 7 Dump Coverage and Session Handoff Implementation Plan

> **For agentic workers:** Use superpowers:executing-plans inline, with one final independent review. Leave changes uncommitted for the user's manual commit. Execute only after approval of this plan.

**Goal:** Produce a reproducible account of the frames and sessions present in the fixed Twister dump, retain unresolved coverage obligations, and hand immutable training-session identities to Task 8.

**Architecture:** Read an existing immutable corpus revision using Task 5 APIs. Build a deterministic coverage manifest from capture provenance and ordered occurrences, with resumable progress saved outside the corpus database. This build does not launch an emulator or acquire new frames.

**Tech Stack:** Existing Python standard library, corpus store, JSON, pytest. No new dependencies or native builds.

**Spec:** Original Task 7 in `docs/superpowers/plans/2026-11-18-dmd-mask-optimizer.md`; coverage rules in sections 4 and 18 of `DMD_Mask_Optimizer_Design_and_Implementation_Plan.md`; approved static-input constraints in `2026-11-25-task-6-vpinmame-dump-import.md`.

## Scope decision

The user's approved dump-only acquisition replaces the original Task 7 emulator exploration, switch scripts, NVRAM replay, and ROM-only execution requirements for this build. Preserve their purpose as explicit coverage obligations rather than implementing an emulator controller. This is completion of the revised Task 7, not implementation of exhaustive ROM exploration.

The original spec's aspiration for complete ROM coverage cannot be achieved from a supplied dump alone. Report captured scope, unknown reachable total, and unresolved configuration/gameplay domains. Do not infer languages, gameplay modes, or initial machine state from frame appearance.

## Global Constraints

- Canonical source: `C:\DMD Colorization\DMD Mask Optimizer V4\twst_405.txt`; SHA-256 `f711aec5d42fdc423ca02bfd2c8f05c158afaee27a97acdbf59d532b81095b11`; 60,285,082 bytes.
- Expected corpus: 14,443 occurrences, 10,301 unique frames, 4,142 repeated occurrences, one timestamp session. The 15,291-record live VPinMAME dump is historical evidence only and must not be used.
- Reuse an existing corpus only after validating its recorded source hash and profile identity. If none qualifies, import the canonical file once with Task 4/5 APIs. Hash before and after import; a mismatch fails qualification.
- Preserve occurrence order, repeats, source offsets, ticks, and capture/session boundaries. Timestamp units remain unknown.
- `Revision.complete` means source intake completed; it never establishes complete ROM coverage.
- Do not split a single capture into purportedly independent training and validation data. This build has no independent validation capture; report that gap.
- All output/checkpoints go under a fresh `artifacts/task7-<run-id>/` directory in the worktree. No VPinMAME, ColorizingDMD, registry, or source-dump writes.

## Review Focus

1. Unknown metadata stays unknown; a clean import never becomes evidence of a tested language or game mode.
2. Repeated frames and overlapping frames across sessions retain all occurrences while unique counts use frame identity.
3. Resume on a different corpus/profile/algorithm identity fails before output publication.
4. Interrupted output and malformed checkpoints cannot be accepted as completed coverage evidence.
5. A single source cannot masquerade as independent validation data or exhaustive ROM coverage.

## Files and Contracts

- Create `src/dmd_optimizer/explore/__init__.py` and `explore/coverage.py`: immutable report/session types and deterministic corpus summarization.
- Create `src/dmd_optimizer/explore/frontier.py`: atomic progress checkpoints and resume identity checks; retains unresolved obligations rather than executable emulator actions.
- Create `tests/unit/test_coverage.py`, `tests/integration/test_exploration.py`, and `tests/local/test_twister_coverage.py`.
- Create `docs/superpowers/evidence/task-7-dump-coverage.md`.
- Add `read_capture_metadata(project: Path, revision_digest: str) -> tuple[CaptureMetadata, ...]` to `corpus/store.py` and export it from `corpus/__init__.py`. Frozen `CaptureMetadata` has `capture_id: str`, `ordinal: int`, `source: Capture`. Read only captures linked to the requested revision, in revision order. Use a read-only SQLite connection so an inspection of a missing corpus cannot create one. Validate decoded provenance through the existing source validator.

`SessionSummary` is frozen: `capture_id: str`, `session: int`, `occurrence_count: int`, `unique_frame_count: int`, `first_index: int`, `last_index: int`, `first_tick: int`, `last_tick: int`.

`CoverageReport` is frozen: `schema_version: int` (1), `algorithm_version: str` (`dump-coverage-v1`), `revision_digest: str`, `rom_sha256: str`, `profile_sha256: str`, `capture_count: int`, `occurrence_count: int`, `unique_frame_count: int`, `repeat_count: int`, `sessions: tuple[SessionSummary, ...]`, `training_sessions: tuple[tuple[str,int], ...]`, `validation_sessions: tuple[tuple[str,int], ...]`, `total_reachable: int | None`, `coverage_status: str`, `obligations: tuple[str, ...]`, `source_scope: str`.

For this initial build all observed sessions are training sessions; validation_sessions is empty. total_reachable is always None; coverage_status is `observed-only`; source_scope is `supplied-dumps`. Obligations always include `reachable-output-domain-unproved`, `language-settings-domain-unknown`, `initial-state-domain-unknown`, `gameplay-mode-coverage-unproved`, `independent-validation-capture-missing`, and `timestamp-unit-unknown`. Intake completeness and analysis completion are separate from this coverage status.

Public API: `summarize(project: Path, revision_digest: str, checkpoint_path: Path, stop: Callable[[], bool]) -> CoverageReport | None`. It returns None after cancellation with a valid checkpoint; it returns a report only after consuming and validating the whole revision. Session keys are `(capture_id, session)`, never session number alone.

## Unit 1: Read provenance and summarize observed sessions

**Consumes:** Task 5 `read_revision`, `iter_occurrences`, and stored capture provenance.
**Produces:** CoverageReport and immutable Task 8 session keys.

- [ ] Write `test_capture_metadata_is_revision_scoped`: append two generated captures, read the older revision, and assert it returns only the first capture with unchanged provenance. Missing corpus and revision fail without creating a database. Invalid JSON/provenance fails with a named corpus error.
- [ ] Run `python -m pytest tests/unit/test_coverage.py -q -p no:cacheprovider`. Expected: failure for missing metadata/summarize API.
- [ ] Implement the read-only metadata API. Do not change the SQLite schema or existing capture identity calculation.
- [ ] Write `test_counts_repeats_and_separate_sessions`: fixture capture A has pixel records A,A,B with ticks 10,10,3; capture B has B,C at ticks 1,2. Require five occurrences, three unique frames, two repeats, three session keys, preserved zero tick delta, and no fabricated duration across captures or resets.
- [ ] Write `test_unknown_domains_remain_unproved` and `test_single_capture_has_no_independent_validation`: assert the exact status, null total, empty validation sessions, and obligations defined above even when Revision.complete is True. Assert no coverage percentage is emitted.
- [ ] Implement session/count aggregation using frame IDs, retaining occurrence counts separately. Compare computed totals with Revision totals; reject disagreement or capture identities inconsistent with the report ROM/profile. Memory may hold distinct frame IDs and session counters, never all native pixel payloads.
- [ ] Rerun the focused tests. Expected: all pass.

## Unit 2: Resume safely and publish the coverage manifest

**Consumes:** Unit 1 ordered metadata and occurrences.
**Produces:** atomic checkpoint and final coverage JSON.

- [ ] Write `test_resume_matches_uninterrupted`: stop after two occurrence visits in the generated fixture, resume, and compare canonical final report bytes with an uninterrupted run. Include cancellation before the first occurrence and at the final occurrence.
- [ ] Write `test_checkpoint_identity_and_corruption`: reject changed revision, profile, algorithm version, invalid counts/cursor, malformed JSON, and checksum mismatch. Leave any previous completed report unchanged on failure.
- [ ] Implement frontier checkpoints containing schema/algorithm versions, ROM/profile/revision digests, next ordinal, accumulated counts/session counters/frame IDs, and a checksum over canonical JSON excluding the checksum field. Store no file timestamps or run IDs in semantic report content. Validate checkpoint counters by replaying the processed prefix; resume must neither skip nor double count. Prefix replay is acceptable at this corpus size.
- [ ] Write checkpoints using a sibling temporary file and atomic replacement. Publish final `coverage.json` only after iteration, count reconciliation, and stop handling finish. Reopening it must reconstruct the same typed report. A malformed checkpoint fails explicitly rather than silently restarting.
- [ ] Run `python -m pytest tests/unit/test_coverage.py tests/integration/test_exploration.py -q -p no:cacheprovider`. Expected: uninterrupted and resumed manifests match; all cancellation/identity cases pass.

## Unit 3: Qualify the fixed Twister corpus and record Task 8 handoff

**Consumes:** canonical static dump or a provenance-verified revision of it; Units 1–2.
**Produces:** coverage.json, checkpoint/resume transcript, local evidence, Task 8 training-session identities.

- [ ] Add `tests/local/test_twister_coverage.py`, gated by `DMD_TWISTER_DUMP`. An unset variable may skip CI; an explicitly missing/wrong-hash path fails. The qualification command must set the variable to the canonical project file. Reuse one module-scoped corpus import for local cases.
- [ ] Assert the exact locked source hash, 14,443 occurrences, 10,301 unique frames, 4,142 repeats, one session, ticks `0x00088b41` through `0x00227c3f`, null reachable total, observed-only status, and empty validation sessions. Assert file SHA is unchanged after processing.
- [ ] Verify one cancellation/resume against the same corpus and require canonical report equality with uninterrupted processing. Save the corpus revision digest, capture/session keys, source hash, report hash, counts, obligations, and actual command in evidence. Label capture producer/version unknown where unrecorded; do not invent provenance.
- [ ] Run the qualification using the existing venv: `$env:PYTHONPATH='artifacts/task3-test-deps;src;.'; $env:DMD_TWISTER_DUMP='C:\DMD Colorization\DMD Mask Optimizer V4\twst_405.txt'; & 'C:\DMD Colorization\DMD Mask Optimizer V4\.venv\Scripts\python.exe' -m pytest tests/unit/test_coverage.py tests/integration/test_exploration.py tests/local/test_twister_coverage.py -q -p no:cacheprovider --basetemp=artifacts/task7-focused`. Expected: all enabled cases pass, including the real static dump.
- [ ] Run the full suite once using the same interpreter/environment with `-q -p no:cacheprovider --basetemp=artifacts/task7-full`; retain logs and exit status, and record all failures/skips. Poll the actual process session to completion; absence of process output alone is not success evidence.
- [ ] Obtain one final independent review of this task, resolve demonstrated correctness issues, run `git diff --check`, and copy this plan and evidence to the main project's matching local docs folders. Leave source changes uncommitted.

## Completion and Task 8 Handoff

Complete when the static corpus has a deterministic, reopened coverage manifest; resumed processing equals uninterrupted processing; unknown coverage stays explicit; and the local qualification and review results are saved. Task 8 consumes the exact corpus revision and observed training-session keys. With no independent validation capture, family generalization remains provisional and uncertain groups retain separate references.

## Execution record (2026-11-25)

Implemented without writes to ColorizingDMD, VPinMAME, the registry, or the
static source dump. Final review remediation added complete prefix validation
(including zero-cursor checkpoints), corpus-order restoration on resume,
streaming traversal, and read-only inspection access. The focused post-review
verification passed: `7 passed in 2.92 seconds`.

## Efficiency

Use one executor and one final review. Reuse the locked corpus by digest, perform at most one fresh import for qualification, and save command logs/result JSON in the run directory. Do not repeat PinMAME API investigation, native builds, UI automation, or the superseded live-recorder tests to complete this task.
