# Task 4 Dump Import Implementation Plan

> **For agentic workers:** Use superpowers:executing-plans for one implementation pass and one final independent review. Steps use checkbox syntax for tracking. Preserve the user's preference for efficient execution and manual commits.

**Goal:** Stream every Twister dump occurrence without losing pixel values, repeats, source positions, or timestamp uncertainty.

**Architecture:** A binary-line parser validates one complete record at a time and yields immutable occurrence records with one-record lookahead for duration. Timestamp interpretation is explicit profile data; unverified units remain raw ticks. Task 5 will persist and deduplicate the resulting occurrences.

**Tech Stack:** Existing Python environment, standard library, pytest; no new runtime dependencies or native/UI automation.

**Spec:** `DMD_Mask_Optimizer_Design_and_Implementation_Plan.md`, sections 6 and 22; Task 4 in `docs/superpowers/plans/2026-11-18-dmd-mask-optimizer.md`.

## Execution result — 2026-11-24

Completed. The strict reader qualified the locked Twister dump: 14,443
occurrences, 4,142 repeats, one monotonic session, and exact native shades.
Timestamp units remain unverified and are represented as null rather than
inferred. Final verification reported `138 passed, 17 skipped in 40.90s`.

## Global Constraints

- Twister `twst_405`, width 128, height 32, four native shades `0` through `3`; output pixels are 4,096 row-major bytes with values 0 through 3.
- Expected local dump SHA-256: `f711aec5d42fdc423ca02bfd2c8f05c158afaee27a97acdbf59d532b81095b11`; 14,443 occurrences; first tick `0x00088B41`, last tick `0x00227C3F`.
- Local fixture: `C:\DMD Colorization\DMD Mask Optimizer V4\twst_405.txt`. It is absent from this worktree root; do not recopy it or commit its content.
- Preserve original occurrence order, repeated frames, ticks and byte offsets. Do not rescale, recolor, filter, deduplicate or infer missing frames.
- Accept only the verified timestamped text grammar. ZIP/raw adapters and diagnostic salvage are deferred; strict failure is the only import mode in Task 4.
- Timestamp units must be verified, not assumed. Parsing can complete with unknown units; timed replay remains unavailable until supported by producer evidence.
- All generated tests use synthetic pixels. Evidence and temporary data stay under `artifacts/task4-<run-id>/` in the worktree. No existing colorization project or registry changes are needed.
- Preserve uncommitted Task 3 changes. Save documentation and source locally; the user will commit manually.

## Review Focus

1. Paired 31/33-row records must fail individually even though their average height is 32 (Step 1).
2. Truncated EOF, extra rows, missing delimiters and non-ASCII symbols must report the offending source position (Step 1).
3. Duplicate or decreasing timestamps must preserve occurrences without silently inventing elapsed time (Step 2).
4. A reset and a 32-bit wrap must not be guessed from decreasing ticks without an explicit producer policy (Step 2).
5. The real file must be streamed with bounded memory and compared to its locked identity; a skipped local test cannot certify Task 4 (Step 3).

---

## Files and Contracts

- Create `src/dmd_optimizer/capture/__init__.py`.
- Create `src/dmd_optimizer/capture/text_dump.py`: strict grammar, immutable occurrence/timing types, typed parse errors and streaming iterator.
- Create `tests/unit/test_text_dump.py`: generated grammar, byte-position, repeat and timing cases.
- Create `tests/local/test_twister_dump.py`: complete local fixture qualification, gated by `DMD_TWISTER_DUMP`.
- Create `docs/superpowers/evidence/task-4-dump-import.md`: grammar, producer/timing findings, hashes, counts and commands.
- Modify `profiles/twst_405.json` and `scripts/lock_profile.py` only to add and validate the explicit `dump_format` profile contract below; extend `tests/integration/test_profile.py` accordingly.

Public interface in `capture/text_dump.py`:

`read_dump(path: Path, profile: Profile) -> Iterator[OccurrenceInput]`

`OccurrenceInput` is a frozen dataclass with `session: int`, `index: int` (global zero-based order), `original_tick: int`, `duration_ticks: int | None`, `duration_status: str`, `offset: int` (header byte offset), `end_offset: int` (exclusive end of record including delimiter), `line: int` (one-based header line), and `native_pixels: bytes`. Session numbering begins at zero. The iterator owns and closes its file handle, including on parse failure or explicit iterator close.

`DumpParseError(ValueError)` exposes `path: Path`, `offset: int`, `line: int`, `record_index: int`, and `code: str`. Its message includes these positions and the invalid condition. EOF errors use the EOF byte offset. Do not load the complete file into memory to obtain positions.

Add `Profile.dump_format` to the existing dataclass and profile validator. The JSON object contains `grammar: "timestamped-text-v1"`, `tick_bits: 32`, `tick_unit: null`, `discontinuity_policy: "split-unknown"`, and `timing_evidence: []`. Existing fixture profile builders must inherit this field. `tick_unit` may become `"milliseconds"` only with recorded producer evidence; validate the allowed values. No downstream API accepts fabricated milliseconds.

## Step 1: Strict, Streaming Record Parser

- [ ] Inspect the local fixture's first/last records and line endings using a bounded binary read. Record the observed delimiter and whether the final record ends with its delimiter. Do not treat the whole file's total row count as validation.
- [ ] Write generated tests named `test_reads_native_shades_and_repeats`, `test_preserves_byte_offsets_for_lf_and_crlf`, `test_rejects_paired_31_33_rows`, `test_rejects_invalid_record`, and `test_iterator_closes_file`. Assert pixel order with distinct corner values and repeated occurrences with different indices. Parameterize invalid records: 127/129 columns, 31/33 rows, symbol `4`, symbol `g`, non-ASCII byte, malformed/overflow timestamp, missing blank delimiter, empty file and truncated EOF. Assert error code, index, line and byte offset.
- [ ] Run `python -m pytest tests/unit/test_text_dump.py -q -p no:cacheprovider --basetemp=artifacts/task4-unit-red`. Require a failure attributable to the absent parser, then implement the interface.
- [ ] Parse files in binary mode. Require headers `0x` followed by exactly eight hexadecimal digits, 32 pixel rows of exactly 128 ASCII symbols `0` through `3`, and the verified empty-line separator. Accept LF and CRLF; reject bare CR, BOM, padded rows and stray text. Case-insensitive hex digits are allowed; do not trim payload whitespace. A complete final record requires its separator; missing rows or separator at EOF raise an error. Yield only fully validated records.
- [ ] Implement bounded reads (maximum valid line length plus terminator and one overflow byte), running byte/line positions, and at most two records in memory. Convert ASCII shades by subtracting `ord('0')`; no normalization beyond line terminator removal.
- [ ] Run the unit command with `artifacts/task4-unit-green`; require every grammar and position assertion to pass.

**Deliverable:** strict record parsing with actionable positions and preserved raw payloads.

## Step 2: Explicit Timestamp and Session Semantics

- [ ] Write `test_positive_and_equal_ticks`, `test_decrease_splits_unknown_session`, `test_wrap_is_not_guessed`, `test_final_duration_unknown`, and profile validation cases. For ticks `[10, 15, 15, 3, 8]`, assert sessions `[0,0,0,1,1]`, durations `[5,0,None,5,None]`, statuses `['observed-delta','observed-delta','discontinuity','observed-delta','final-unknown']`, and unchanged original ticks. For `[0xfffffffe,1]`, require a new session and unknown duration across the boundary under `split-unknown`. Assert invalid policy, tick width and unsupported units fail profile validation.
- [ ] Run the focused unit/profile tests and observe the missing timing/profile behavior; implement the stated dataclass/profile contract and one-record lookahead. Equal ticks retain both calls with zero duration. Any decreasing tick under this initial policy closes the prior session with unknown duration and starts the next session; it does not claim a proven reset or wrap.
- [ ] Inspect the already selected producer source or available local producer evidence once for timestamp units and wrap/reset behavior. Record exact source revision and symbol if conclusive. Do not estimate units from numeric magnitudes or frame cadence. If inconclusive, retain null units and report the limitation; no dependency download or UI work is required for parser completion.
- [ ] If evidence establishes different semantics, add the specific policy and failing example before implementing it. Keep the conservative policy as a supported fallback and preserve the raw ticks in every policy. Do not widen supported behavior merely to make the real file pass.
- [ ] Rerun the focused tests; require all cases to pass and no invented negative or huge duration at discontinuities.

**Deliverable:** lossless occurrences suitable for Task 5, with explicit timing uncertainty.

## Step 3: Qualify the Complete Twister Dump and Record Handoff

- [ ] Write `tests/local/test_twister_dump.py`. Skip only when `DMD_TWISTER_DUMP` is unset; an explicitly configured missing path fails. Stream SHA-256 and compare to `profile.dump_sha256`, then fully consume `read_dump`. Assert 14,443 records, 4,096 pixels each, shades exactly `{0,1,2,3}`, first/last ticks `0x00088B41`/`0x00227C3F`, sequential indices, increasing non-overlapping source ranges, and final `end_offset` equal to file size. Collect counts and the first malformed position; do not retain all pixels in a list.
- [ ] Run the local test before implementation is finalized and after corrections. Configure PowerShell with `$env:DMD_TWISTER_DUMP = 'C:\DMD Colorization\DMD Mask Optimizer V4\twst_405.txt'`. Use the established Python executable if `python` resolves elsewhere: `C:\DMD Colorization\DMD Mask Optimizer V4\.venv\Scripts\python.exe`. Reuse `artifacts/task3-test-deps` in `PYTHONPATH` if needed; do not reinstall dependencies.
- [ ] Run `python -m pytest tests/unit/test_text_dump.py tests/local/test_twister_dump.py tests/integration/test_profile.py -q -p no:cacheprovider --basetemp=artifacts/task4-focused`. Require all parser/local cases to execute and pass. Existing separately gated native profile tests may remain skipped and must be listed separately.
- [ ] Write the evidence document with input hash, grammar/line endings, record and shade counts, first/last ticks, repeat count, session/discontinuity counts, timing status, streamed payload digest, input byte size, elapsed time, and observed peak memory. Measure peak memory once during the existing qualification run; no separate performance framework. Describe repeats by full raw pixel equality; occurrence preservation remains mandatory.
- [ ] Run the complete suite once with the existing Task 3 native worker/decoder environment retained: `python -m pytest -q -p no:cacheprovider --basetemp=artifacts/task4-full`. Record passes, skips and every failure. Fix demonstrated issues and rerun only affected tests before the final suite when a code change warrants it.
- [ ] Obtain one independent milestone review of parser, timing, profile changes and evidence. Address concrete correctness findings. Run `git diff --check`, update this plan's completion record, and leave all changes uncommitted for the user.

**Completion gate:** the locked local file passes strict per-record validation; every occurrence survives in order with native bytes, source positions and explicit timing status; malformed synthetic inputs fail at precise positions; full-suite results and review findings are recorded. Unknown tick units restrict timed playback but do not block lossless import. Optional salvage and additional formats remain outside this task.

**Next task:** Task 5 consumes `OccurrenceInput` to store immutable corpus revisions. Keep deduplication, SQLite storage and frame identity hashing in Task 5.
