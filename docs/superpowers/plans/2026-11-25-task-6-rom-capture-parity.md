# Superseded: Task 6 ROM Audit and Capture Parity Implementation Plan

> **Superseded on 2026-11-25.** The installed VPinMAME distribution provides
> the supported DMD dump workflow (`DmdDump`/F6 and `DmdDevice.ini`
> `rawoutput`). Task 4 already implements the lossless timestamped-text reader
> needed by the optimizer. Do not build or qualify an independent live recorder
> from this plan. The replacement is
> `docs/superpowers/plans/2026-11-25-task-6-vpinmame-dump-import.md`.

> **For agentic workers:** Use `superpowers:executing-plans` for inline implementation, with one final independent review. Steps use checkboxes for tracking. Preserve existing uncommitted work and leave this task uncommitted for the user's manual commit.

**Goal:** Audit the selected Twister ROM by content and certify lossless native identification capture against the runtime input from the same controlled PinMAME run.

**Architecture:** Python validates archive content and launches an isolated Windows x64 worker. The worker uses the pinned PinMAME source/API at the identification delivery boundary, recording separate capture and runtime-consumer traces before display transforms. Python validates these traces and exposes occurrences through the Task 4/5 interface; support is certified only after real same-run parity succeeds.

**Tech Stack:** Existing Python environment, standard-library ZIP/hash/subprocess tools, C++/MSVC, pinned PinMAME 3.6, existing corpus store.

**Spec:** `DMD_Mask_Optimizer_Design_and_Implementation_Plan.md`, sections 6 and 22; Task 6 in `docs/superpowers/plans/2026-11-18-dmd-mask-optimizer.md`.

## Global Constraints

- Initial support is Twister `twst_405`, profile driver `de_mSES1`, 128x32, native shade values 0–3. Verify this profile driver against pinned native metadata; do not silently substitute a guessed driver name.
- Preserve repeats, order, native timestamps, reset boundaries, and raw native pixels. Reject luminance-only delivery and every unqualified geometry/encoding.
- Baseline source commit: `ecd032e55481b261cce4820b53fd28fe478c70b4`; pinned Windows x64 VPinMAME SHA-256: `69ebacabdb7e1af0533142a8456341f06e9d4b6cb3dc4649f18794be456ea8c1`. Reuse the full dependency locks in `profiles/twst_405.json`.
- ROM: `C:\DMD Colorization\DMD Mask Optimizer V4\twst_405.zip`; supplied dump is a separate reference input, never evidence of same-run live parity.
- Store all native state, copied dependencies, traces, ROM staging and corpora under this worktree's `artifacts/task6-<run-id>/`. Do not use installed emulator NVRAM, registry paths, or existing colorization projects. Disable external display/device/network outputs for the qualification run.
- No dependency installation, external configuration change, merge, push or automatic commit is part of this task. Request required sandbox escalation through the normal tool approval mechanism.
- Capture duration is bounded. Completion means the declared observed run passed; it does not establish full-ROM coverage or language/settings coverage.

## Review Focus

1. A renamed ZIP must resolve to the same driver by member identity; a ZIP with the expected filename but wrong content must fail (Unit 1).
2. A display/luminance callback can look plausible while losing native shades; qualification must establish the hook's native semantics from source and executable traces (Unit 2).
3. Two logs generated from one copied buffer do not independently prove parity; instrument the capture tap and the actual runtime input boundary separately (Units 2–3).
4. A repeated frame, clock reset, truncated trace or missing tail must remain visible and must not pass an abbreviated comparison (Unit 3).
5. Timeout, crash and cancellation must stop the worker and leave existing application state untouched; no partial run may be certified (Units 2–3).

## Files and Contracts

- Create `src/dmd_optimizer/rom/__init__.py` and `rom/audit.py`: archive inventory and native driver audit.
- Create `src/dmd_optimizer/capture/live.py`: worker lifecycle, protocol validation, trace comparison and occurrence stream.
- Create `native/pinmame_worker.cpp`; modify `native/CMakeLists.txt` to add an independent worker target.
- Create `schemas/pinmame-worker-v1.json`: request/result manifests. Keep this separate from the Serum worker protocol.
- Create `tests/unit/test_rom_audit.py`, `tests/unit/test_live_capture.py`, `tests/integration/test_pinmame_worker.py`, `tests/local/test_twister_capture.py`.
- Create `docs/superpowers/evidence/task-6-rom-capture-parity.md`.
- Modify `profiles/twst_405.json` only for demonstrated corrections or a separately recorded qualified live-delivery block; never replace original vendor binary hashes with an instrumented build hash.

Python contracts (frozen dataclasses; paths are `Path`):

```python
audit_rom(path: Path, profile: Profile) -> AuditResult
capture(session: CaptureRequest) -> Iterator[OccurrenceInput]
compare_traces(capture_path: Path, consumer_path: Path) -> ParityResult
```

`AuditResult`: `rom_path`, `archive_sha256`, `content_sha256`, `profile_sha256`, `revision`, `driver`, `members`, `dependencies`, `native_audit_digest`. `members` and `dependencies` are tuples of validated immutable inventory records. Audit output binds the actual archive bytes, selected profile and native metadata report.

`CaptureRequest`: `audit: AuditResult`, `profile: Profile`, `worker: Path`, `runtime_dir: Path`, `output_dir: Path`, `settings: dict`, `input_schedule: tuple[InputEvent, ...]`, `stop_after_ms: int`, `timeout_ms: int`. `InputEvent` contains `at_ms: int`, `switch: int`, `closed: bool`. Schedule times must be nonnegative, ordered and within the stop limit; switch IDs must be verified for this driver. Validate the audit/profile binding and rehash ROM/dependencies before launch.

`ParityResult`: `passed: bool`, `occurrence_count: int`, `first_divergence: dict | None`, `capture_sha256: str`, `consumer_sha256: str`, `session_id: str`. Diagnostics distinguish count, pixel, geometry, encoding, timestamp and order mismatches. A mismatch never produces a support certificate.

Use `CaptureError(ValueError)` / `RomAuditError(ValueError)` with actionable named paths, member/driver names and chained causes. Preserve native diagnostics and return codes.

## Task 1: Bounded Native Preflight and ROM Audit

**Consumes:** locked `Profile`, ROM inventory helpers in `scripts/lock_profile.py` and the pinned source/build metadata.
**Produces:** `AuditResult` and a source-backed hook/build decision consumed by Task 2.

- [ ] Inspect the existing staged toolchain and pinned source only once. Record exact paths, hashes, headers, exported APIs, audit entry point, driver lookup and raw identification delivery call site in the evidence document. Inspect the runtime input boundary used by the pinned integration. Do not infer APIs from DLL filenames or substitute a display callback.
- [ ] Choose the smallest verified build route: use the pinned API if it exposes both audit and raw delivery; otherwise compile an instrumented pinned source build with a narrow worker bridge. Record patch, build commands, flags and produced hashes separately. If the source is absent, obtain that exact revision through approved network tools. If neither route can expose a real runtime boundary, record that precise dependency as unresolved; synthetic parity is not a substitute for completion.
- [ ] Write synthetic ZIP tests: renamed archive succeeds by member content; wrong expected member bytes, missing CPU/display/sound member, duplicate case-insensitive names, malformed ZIP and unsupported driver fail with named diagnostics. Verify parent dependency resolution using generated parent/clone metadata; Twister's actual parent requirements come from native audit, not an assumed empty list. Reject path traversal and ambiguous archives.
- [ ] Run `python -m pytest tests/unit/test_rom_audit.py -q -p no:cacheprovider --basetemp=artifacts/task6-audit-red`. Expected: missing module/API failure.
- [ ] Implement `audit_rom` and native audit request/result mode. Match the manifest by sorted member content, sizes and hashes, independent of outer ZIP filename or compression. Retain actual archive SHA separately. Stage a canonical driver-named archive only inside the owned run directory if native loading requires that filename. Let native audit validate driver and dependencies before capture starts.
- [ ] Run the audit tests again and the generated native audit smoke case. Expected: all synthetic assertions pass; native report names the pinned metadata/build and resolved driver. Save the command and result in the ledger.

## Task 2: Isolated Native Worker and Ordered Live Stream

**Consumes:** Task 1 audited ROM and source-backed hook decision; existing `OccurrenceInput` contract.
**Produces:** bounded worker capture and consumer trace files plus `capture()` occurrences.

- [ ] Write generated worker/protocol tests for A,A,B, native shade values 0–3, equal timestamps and a timestamp decrease. Require all three occurrences; indices start at zero, sessions increment on decreases, previous duration is null at discontinuity, and final duration is null. Fake-worker tests must exercise malformed output, wrong profile/ROM/run IDs, worker nonzero exit, timeout and generator closure.
- [ ] Run `python -m pytest tests/unit/test_live_capture.py -q -p no:cacheprovider --basetemp=artifacts/task6-live-red`. Expected: missing live API failures.
- [ ] Define version-1 trace framing in `live.py` and worker code: magic `DMDLIVE1`, little-endian 32-bit metadata length, canonical UTF-8 JSON metadata, then records with little-endian 32-bit record length, 64-bit sequence, 64-bit native tick, 16-bit width/height/shade count, 32-bit payload length and raw native-u8 bytes. Validate exact record size and file EOF. Bound metadata to 64 KiB and payload to the supported geometry. Metadata binds session ID, stream role, ROM/content/profile/build/patch digests, timestamp clock source and unit, encoding, hook location and source coordinate order. Never label ticks milliseconds without verifying the native clock contract.
- [ ] Add explicit completed-run manifests containing trace hashes, record counts, schedule actually applied, initial-state hashes, stop reason, settings and worker/runtime identities. Atomically publish a completion manifest only after both streams close successfully. Missing completion manifest is an incomplete run even if the trace parses.
- [ ] Implement the worker in a child process with copied/staged dependencies and owned state directories. Use documented engine stop and join before process exit; Python enforces a wall-clock deadline and terminates the process tree on failure. Confirm working directory alone actually redirects NVRAM/config; if it does not, use verified native path options before running. Reject unsafe launch configuration.
- [ ] Instrument capture at the native identification hook and consumer at its real handoff boundary, with separate record writers. Record repeated calls and timestamps at their native origin. Document any native-to-runtime transformation and prove it lossless in the supported domain. Do not manufacture the consumer trace by copying or replaying the capture log.
- [ ] Implement `capture()`: validate the completed worker run and parity before yielding its persisted capture trace. `offset`, `end_offset` and `line` are record byte bounds and one-based record ordinal in that trace, explicitly documented in provenance. Convert adjacent tick differences conservatively as in Task 4; do not deduplicate.
- [ ] Run unit and native generated-stream integration tests. Expected: valid A,A,B is lossless; malformed/unsupported/incomplete output fails; stopped workers leave no children. Existing Serum/editor targets still build.

## Task 3: Same-run Twister Qualification and Corpus Handoff

**Consumes:** Tasks 1–2 and `corpus.append_capture(project, source, occurrences)`.
**Produces:** archived same-run parity evidence, an isolated corpus revision and a scoped support certificate for Task 7.

- [ ] Write `compare_traces` tests for exact equality, an altered pixel, missing repeated call, extra trailing call, changed clock, reset, mismatched run/build IDs, truncated record and luminance encoding. Equality includes every occurrence and complete metadata semantics, not just unique frame hashes. Persist the first divergence and both trace identities on error.
- [ ] Add `tests/local/test_twister_capture.py` gated by explicit ROM, worker and runtime paths; missing variables may skip normal CI but must not certify this task. Require `audited_revision == 'twst_405'`, a positive occurrence count and exact ordered capture/consumer equality in one run.
- [ ] Run the new tests red before implementation. Implement the comparator and complete-manifest checks, then run generated cases green.
- [ ] Run a bounded 30-second fresh-state boot/attract capture, with a 60-second process deadline, in an empty owned state directory. Use no arbitrary switch events for this minimum qualification. Add a second 30-second run with one verified start/coin switch sequence if native driver metadata/source establishes it; record the exact IDs and application times. Never invent switch numbers or claim play coverage from attract frames.
- [ ] Verify the real ROM audit, native driver, geometry, shade values, independent hook locations, nonempty trace count, exact bytes/order/timestamps and completion status. Archive both original traces, manifests, build/patch identity, first-divergence diagnostic (null on success), settings and initial-state hashes. A failed local test remains a failed qualification, not an allowed skip.
- [ ] Append the qualified capture through Task 5. Hash its immutable capture trace for `Capture.source_sha256`; retain ROM archive/content identity, source/profile/build digests, settings, schedule and clock semantics in provenance. Reopen the resulting revision and compare every occurrence and frame byte with the trace; ensure repeats and resets survive. Certify completeness only for the declared bounded capture.
- [ ] Write a qualification certificate under the run artifact directory keyed by ROM content, profile, driver, native build/patch and delivery contract. Keep it separate from the original vendor profile locks. Task 7 must require this certificate and its trace hashes rather than trusting a global supported flag.
- [ ] Run focused tests with the explicit fixture environment: `python -m pytest tests/unit/test_rom_audit.py tests/unit/test_live_capture.py tests/integration/test_pinmame_worker.py tests/local/test_twister_capture.py -q -p no:cacheprovider --basetemp=artifacts/task6-focused`. Expected: all enabled cases pass, and the real Twister case executes.
- [ ] Run the full suite once with existing native fixture environment retained: `python -m pytest -q -p no:cacheprovider --basetemp=artifacts/task6-full`. Use `C:\DMD Colorization\DMD Mask Optimizer V4\.venv\Scripts\python.exe` and this worktree's `artifacts/task3-test-deps;src;.` in `PYTHONPATH`. Record all pass/fail/skip counts. Repeat only for changed code or unresolved failures.
- [ ] Record audit digests, callback source locations, launch/build commands, trace counts, native clock semantics, elapsed time, peak process memory, cleanup outcome, corpus revision and actual exercised scope in the evidence document. Obtain one final independent review and address demonstrated correctness findings. Run `git diff --check` and save final plan/evidence copies to the main project's matching `docs/superpowers/` folders. Leave all source changes uncommitted.

## Completion Gate

Task 6 is complete only when the real pinned Twister audit and same-run native capture/consumer parity pass, the resulting stream survives a corpus round trip, and worker state stays confined to the owned run directory. Synthetic tests and matching image appearance cannot certify native delivery. If a native dependency prevents the real run, preserve completed code and report the specific unmet gate.

Task 7 receives an audited ROM, a validated `CaptureRequest`, an immutable corpus revision and a qualified delivery certificate. Configuration enumeration, broad exploration and coverage closure remain Task 7 work.

## Efficiency and Resumption

Use three units above in order with one executor and one final reviewer. Record source/API discovery once in `.superpowers/sdd/2026-11-25-task-6-rom-capture-parity/progress.md`; later turns resume from that ledger and saved build manifests. Keep native build outputs and successful audit results reusable by digest. Cap exploratory native probes at one API inspection and one minimal build/smoke attempt per demonstrated hypothesis; unresolved API/build facts should be recorded explicitly before trying another route.
