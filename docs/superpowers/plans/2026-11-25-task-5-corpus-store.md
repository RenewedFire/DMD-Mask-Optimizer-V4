# Task 5 Immutable Corpus Store Implementation Plan

> **For agentic workers:** Use superpowers:executing-plans for inline implementation of the three units below, followed by one independent milestone review. Use checkbox syntax to record progress. Preserve the user's preference for manual commits.

**Goal:** Persist imported captures as immutable corpus revisions with stable frame IDs, lossless occurrences, and recoverable writes.

**Architecture:** SQLite holds capture provenance, frame locations, occurrence order, and revision membership. Immutable binary chunks hold native pixel bytes and are flushed and checksummed before their metadata transaction commits. Existing revisions remain readable when a new capture is appended; revision digests become downstream cache keys.

**Tech Stack:** Existing Python environment; standard-library `sqlite3`, `hashlib`, `json`, file and path APIs; pytest. No new dependency or native/UI operation.

**Spec:** `DMD_Mask_Optimizer_Design_and_Implementation_Plan.md`, sections 6–7 and 15; Task 5 in `docs/superpowers/plans/2026-11-18-dmd-mask-optimizer.md`. Consume the actual Task 4 interface in `src/dmd_optimizer/capture/text_dump.py`.

## Global Constraints

- Use SQLite transactions for metadata and append-only frame chunks for pixel payloads. Write chunks and checksums before committing metadata references. Clean up orphan chunks after interrupted writes.
- All long-running stages use immutable input revisions. New captures create a new revision and invalidate dependent proofs by changing their input digest; do not edit earlier revision membership.
- Preserve every occurrence's original order, session, raw tick, duration status, source offsets, and native pixels. Repeats share storage, not occurrence rows.
- Frame identity includes width, height, shade encoding, normalization version, and raw bytes. Confirm bytes on digest hits. Runtime CRC is a separate attribute, not a deduplication key.
- Initial supported encoding: `native-u8`, normalization `identity-v1`; no pixel transformation. Twister is 128 by 32 with native shades 0–3. Unknown tick units remain null.
- Keep ROMs, dumps, databases, chunks, and generated evidence local under `artifacts/task5-<run-id>/`. Use synthetic inputs in tracked tests. Never target an existing ColorizingDMD project directory.
- Preserve uncommitted Tasks 3–4. Leave implementation uncommitted for the user. No merge, push, installation, registry change, or UI work is required.

## Review Focus

1. Two unequal frames with a forced equal lookup digest must survive as distinct stable IDs (Unit 1).
2. A repeated frame or timestamp reset must retain all occurrences and exact metadata after reopen (Units 1–2).
3. An iterator that raises halfway through import must not expose a partial revision or capture (Unit 2).
4. Process interruption before/after metadata commit must yield either the prior revision or the complete new revision, with no referenced missing chunk (Unit 3).
5. Corrupt chunks, incompatible project identity, and competing writers must fail clearly rather than return a misleading corpus (Units 2–3).

---

## Files and Public Contracts

- Create `src/dmd_optimizer/corpus/__init__.py`.
- Create `src/dmd_optimizer/corpus/store.py`: dataclasses, database initialization, append/read transactions and integrity/recovery entry points.
- Create `src/dmd_optimizer/corpus/chunks.py`: chunk framing, bounded writes, checksums, verified reads and owned orphan handling.
- Create `schemas/corpus-v1.sql`: schema version, constraints, indexes and foreign keys.
- Create `tests/unit/test_corpus.py`: synthetic persistence, identity, metadata, revision and interruption cases.
- Create `tests/local/test_twister_corpus.py`: optional real dump-to-store qualification, gated by `DMD_TWISTER_DUMP`.
- Create `docs/superpowers/evidence/task-5-corpus-store.md`: commands, counts, digests, recovery evidence and limitations.
- Modify Task 4 files only if a demonstrated interface defect blocks persistence; add a reproducing test before any such fix.

Define these frozen dataclasses in `store.py`:

- `Capture(source_sha256: str, source_uri: str, producer: str, producer_version: str | None, configuration: dict, complete: bool, width: int, height: int, native_shades: int, encoding: str, normalization: str, tick_unit: str | None, timestamp_semantics: dict, rom_sha256: str, profile_sha256: str)`. Configuration and timestamp semantics must be JSON-serializable with string keys and finite numbers. For dump imports, timestamp semantics contains the complete `Profile.dump_format` object. Store canonical JSON bytes, not the caller's mutable objects.
- `Revision(digest: str, parent_digest: str | None, capture_count: int, occurrence_count: int, unique_frame_count: int, complete: bool)`; counts cover the entire revision. Completeness is true only if all member captures are complete; it does not imply full-ROM coverage.
- `StoredOccurrence(capture_id: str, frame_id: str, session: int, index: int, original_tick: int, duration_ticks: int | None, duration_status: str, offset: int, end_offset: int, line: int)`; `index` remains capture-local.
- `CorpusError(ValueError)` for invalid input, incompatible schema/project identity, or detected corruption. Preserve underlying I/O/SQLite errors as chained causes with the affected path or operation.

Public functions:

```python
append_capture(project: Path, source: Capture,
               occurrences: Iterable[OccurrenceInput]) -> Revision
read_revision(project: Path, digest: str | None = None) -> Revision
iter_occurrences(project: Path, revision_digest: str) -> Iterator[StoredOccurrence]
read_frame(project: Path, frame_id: str) -> bytes
recover(project: Path) -> None
```

`project` is the corpus-store root. Its layout is `corpus.sqlite3`, `chunks/<uuid>.bin`, and `staging/<uuid>.tmp`. Validate schema version 1 before use; never overwrite an unrelated database. Do not place sidecar files in another application's directory.

`iter_occurrences` orders by revision capture ordinal, then original occurrence index. Every read is bounded to the requested revision; reopening an earlier revision must not include later captures. `read_frame` validates its chunk checksum, record bounds and expected frame identity before returning bytes.

## Task 1: Frame Identity and Lossless Storage

- [ ] Write `test_corpus_roundtrip_preserves_repeated_occurrences`: import synthetic A,A,B; assert two unique frames, three occurrence rows, the first two equal frame IDs, a distinct B ID, exact pixel bytes after closing/reopening, and unchanged timestamps/source positions. Include separate geometry with identical payload bytes to prove distinct identity.
- [ ] Write `test_digest_collision_preserves_unequal_frames` and `test_reimport_keeps_frame_ids`. Force only the lookup-digest helper to return a constant. Assert A and B retain distinct IDs and bytes, and replaying the same import into a fresh store gives the same frame IDs.
- [ ] Run `python -m pytest tests/unit/test_corpus.py -q -p no:cacheprovider --basetemp=artifacts/task5-unit-red`; inspect the expected missing-module/API failure.
- [ ] Implement the schema and frame/chunk primitives. Tables: `project`, `captures`, `frames`, `occurrences`, `revisions`, `revision_captures`, `chunks`. Require foreign keys, unique `(capture_id, occurrence_index)`, unique revision capture ordinals, and indexes for lookup digest and capture ordering. Enable foreign keys for every connection. Use `journal_mode=DELETE`, `synchronous=FULL`, and a five-second SQLite busy timeout for the initial single-writer implementation.
- [ ] Canonical frame input is compact sorted UTF-8 JSON of `[width,height,native_shades,encoding,normalization]`, followed by a NUL byte and pixel bytes. Use SHA-256 as a non-unique lookup bucket and a separately computed SHA-512 of the same input as the stable frame ID. Compare metadata and full bytes on bucket hits. If the stable ID ever names unequal content, raise `CorpusError`; never merge it or invent an import-order-dependent ID.
- [ ] Write chunks in a documented versioned format with record length and raw pixels. Bound each chunk to at most 4 MiB of frame payload, except a single supported frame that itself exceeds the target. Store per-frame byte offsets/lengths and a SHA-256 checksum for each complete chunk. Do not accumulate a whole capture in memory.
- [ ] Implement native input checks: pixel count equals width times height; values fit native shades; indices start at zero and advance exactly by one; sessions start at zero and stay equal or increment by one; ticks, positions, duration statuses and null durations conform to Task 4's contract. Invalid data rolls back the import.
- [ ] Rerun the focused tests; require stable IDs, collision separation, exact payload reads and preserved repeated occurrence metadata.

## Task 2: Immutable Capture Revisions and Atomic Append

- [ ] Write `test_new_capture_preserves_old_revision`, `test_identical_reimport_is_idempotent`, `test_changed_provenance_is_distinct_capture`, `test_iterator_failure_rolls_back`, and `test_rejects_incompatible_project`. Assert old revision counts/order/bytes stay unchanged; identical reimport returns the current revision with no duplicate occurrences; changed configuration or source digest creates a distinct capture; interrupted iteration leaves current revision unchanged; mismatched ROM/profile digests reject append.
- [ ] Add tests for unsupported schema, invalid JSON configuration, invalid occurrence metadata, and incomplete capture provenance. An explicitly incomplete source may import validated supplied occurrences but makes revision completeness false; parser exceptions never silently turn into incomplete success.
- [ ] Run the added cases and confirm failures attributable to missing revision behavior.
- [ ] Derive capture ID from canonical provenance plus the ordered occurrence stream digest. Include every stored occurrence metadata field and stable frame ID in that digest. Identical source bytes with different configuration, producer, completeness or timing policy remain distinct. Source URI is provenance and participates in capture identity. Exclude temporary paths and database row IDs from frame/revision identity.
- [ ] Revision digest is SHA-256 over canonical `[schema_version, rom_sha256, profile_sha256, ordered_capture_ids]`. Parent digest records ancestry; duplicate reimport is a no-op, even if the capture already belongs to an older ancestor. A fresh capture extends the current ordered membership. Do not mutate captures, frame content, membership or revision counts after commit.
- [ ] Implement append under `BEGIN IMMEDIATE`. Consume the iterator once; stage records and metadata within the transaction. Flush and `os.fsync` each completed chunk, close it, and atomically rename to its unique final path before inserting committed chunk references. Insert the new revision and update the current-revision pointer in the same transaction. Roll back SQLite on iterator, validation, disk or database failures. Close iterator/resources in `finally` when supported.
- [ ] Persist project schema version, generated project ID, ROM identity and profile digest on first successful import. Recheck identity inside the write transaction. Serialize concurrent appends through SQLite; report timeout clearly. Use explicit transactions for coherent revision reads.
- [ ] Rerun Task 2 cases and all `tests/unit/test_corpus.py`; require both historical revision readability and atomic publication.

## Task 3: Recovery, Integrity and Twister Qualification

- [ ] Write subprocess interruption tests that stop after chunk flush, after chunk rename, before commit, and immediately after commit. Use test-only monkeypatching at internal I/O boundaries; do not add public fault injection parameters. On reopen, assert current revision is respectively the old or complete new one, prior revisions remain readable, and every referenced frame/chunk passes integrity checks.
- [ ] Add `test_corrupt_or_missing_chunk_fails`, `test_recovery_preserves_referenced_chunks`, and `test_competing_writers_serialize`. Mutate a staged synthetic file or remove a referenced test chunk and require a named corruption error. Race two appenders and assert the final revision contains both successful captures or an explicit timeout, never lost membership.
- [ ] Implement `recover` under the same writer lock. Check SQLite integrity and referenced chunk checksums/bounds. Quarantine unreferenced files from the store-owned staging/chunks directories under `orphans/<run-id>/`; exclude them from all reads. Never delete referenced data or scan outside the resolved corpus root. Recovery cannot recreate missing/corrupt referenced bytes; raise `CorpusError` with the affected chunk.
- [ ] Run the recovery tests; inspect failures before fixing them. Verify quarantined files are recoverable and no current or historical revision loses referenced chunks.
- [ ] Write the local qualification using the actual Task 4 `read_dump` and locked profile. Set `DMD_TWISTER_DUMP` to `C:\DMD Colorization\DMD Mask Optimizer V4\twst_405.txt`; verify its locked SHA-256 first. Store only under the test's artifact directory. Assert 14,443 occurrences, 10,301 unique frames, 4,142 repeated occurrences, exact first/last ticks, one session, final unknown duration, and pixel/metadata equality on a second streaming read. Reimport and assert unchanged IDs, counts and current digest.
- [ ] Configure the existing Python environment; reuse `artifacts/task3-test-deps` in `PYTHONPATH` where required. Run `python -m pytest tests/unit/test_corpus.py tests/local/test_twister_corpus.py -q -p no:cacheprovider --basetemp=artifacts/task5-focused`. The real fixture case must execute; a skip cannot certify the task.
- [ ] Record schema/chunk format, import/reimport commands, input/profile/revision digests, counts, chunk sizes, elapsed time and recovery outcomes in the evidence file. Measure import memory during this qualification; separate parser/store memory from any test verification cache. No million-frame benchmark is required here.
- [ ] Run the full suite once with Task 3 worker/decoder and Task 4 local fixture environment retained: `python -m pytest -q -p no:cacheprovider --basetemp=artifacts/task5-full`. Report every failure and skip; repeat only for changed code or unresolved failures.
- [ ] Obtain one independent final review of Task 5 source, schema, tests and evidence. Fix demonstrated correctness issues, run affected tests and required suite verification, then `git diff --check`. Update the completion record and save the final plan/evidence in the main project folder as previously requested. Leave source changes uncommitted in this worktree.

## Completion Gate and Next Consumer

Task 5 is complete when A,A,B survives as three ordered occurrences/two frame
payloads, collisions cannot merge unequal frames, historical revisions reopen
unchanged, failed imports never publish partial membership, recovery excludes
orphans, and the full local Twister import/reimport passes. Unknown tick units
remain explicit. Task 6 can then append live captures through the same API;
Tasks 8–11 can bind their inputs and cache records to `Revision.digest`.

Family inference, constraints, masks and solver/export artifacts are not yet
implemented: their future records must store the consumed revision digest.
Task 5 establishes that immutable key rather than adding unused subsystem
tables. A new revision never rewrites a prior verification claim.
