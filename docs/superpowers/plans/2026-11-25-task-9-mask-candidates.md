# Task 9 Comparison Mask Candidates Implementation Plan

> **For agentic workers:** Use superpowers:executing-plans inline, with one final independent review. Execute after user approval. Track completed checkpoints and leave changes uncommitted.

**Goal:** Produce a reproducible pool of comparison options that preserve each frozen family domain and reject every incompatible covered input, with concrete witnesses for rejected candidates.

**Architecture:** Consume the static corpus revision and Task 8 family manifest. Generate a bounded deterministic set of candidate bitmaps, check positive invariance and CRC discrimination across the entire declared scope, then save immutable options and rejection evidence for Task 10. Use the normal-comparison byte transform already established in Task 3.

**Tech Stack:** Python standard library, existing corpus/family/profile APIs, zlib CRC32, canonical JSON and pytest. No new dependencies or native builds.

**Spec:** Original Task 9 in `docs/superpowers/plans/2026-11-18-dmd-mask-optimizer.md`; approved design sections 9–11; `AGENTS.md`; Task 8 plan and family manifest contracts.

## Global constraints

- Follow `AGENTS.md`: reuse the immutable corpus imported from `C:\DMD Colorization\DMD Mask Optimizer V4\twst_405.txt`. Import once into the worktree only if no usable capture artifact exists. Source SHA-256: `f711aec5d42fdc423ca02bfd2c8f05c158afaee27a97acdbf59d532b81095b11`.
- Analyze stored records directly. Do not launch VPinMAME, ColorizingDMD, a recorder, folder watcher, interactive qualification process or separate local-dump pytest process. Do not change installed applications or the source dump.
- Twister geometry is 128 by 32 with four native shades. Ignore byte 1 means ignored, 0 means compared; shape mode is always false. Preserve brightness distinctions.
- Save outputs beneath a fresh `artifacts/task9-<run-id>/`. Reuse the same corpus for all stages. All changes remain uncommitted for manual review.
- Freeze family domains and must-compare constraints. Do not split families, discard modeled values or silently weaken constraints to produce savings. Observed-only coverage remains observed-only.
- This task proves option validity for a finite declared scope. Task 10 selects options and enforces the active custom-mask cap; Task 11 verifies exported native artifacts. Do not label this task's analytical checks as a new native replay certification.

## Review focus

1. Different pixel streams with equal CRC32 must be treated as a conflict even when their compared bytes differ (Unit 1 collision test).
2. An incompatible input is offered to every candidate rule, regardless of its own assigned mask (Unit 1 cross-mask negatives).
3. Pairwise-valid unions do not establish a larger union's validity (Unit 2 higher-order test).
4. Same pixels with incompatible contextual expectations may be unrepresentable; matching order cannot resolve them (Unit 1 identical-input test).
5. Stale family manifests, incomplete traversal and invalid persisted caches must never be promoted into verified options (Units 1 and 3 integrity tests).

## Preflight decisions

Task 8's saved evidence does not contain a verified real-data family manifest. Obtain that handoff by direct corpus analysis before declaring Task 9 complete. Do not repeat the abandoned local pytest qualification. Verify capture provenance, ROM/profile/source digests, revision counts and session selection. Expected static totals are 14,443 occurrences, 10,301 unique frames and 4,142 repeats.

The present Task 8 contract sets `must_compare` to all fixed pixels. Honor it. A candidate may ignore every required-ignore position and no must-compare position. With the current partition this permits only the minimum mask for dynamic families; exact observed families permit unmasked options. Synthetic fixtures may use explicitly frozen, less restrictive must-compare subsets to test valid sharing; Task 9 must not generate those relaxed specifications from real data. Report restricted mask sharing honestly. Any broader family policy belongs in a separately approved family revision.

The native oracle API operates on exported projects and starts a worker; it is not a per-candidate hash API. Candidate checking will use the established Task 3 transform plus `zlib.crc32(compared_bytes) & 0xffffffff`, reusing the real CRC collision fixtures from `tests/integration/test_oracle.py`. Task 3's captured compatibility evidence is the provenance for that transform. No editor/worker session is needed to analyze the dump. A changed runtime/profile invalidates this provenance and must yield an unsupported-profile error.

## Files and interfaces

Create `src/dmd_optimizer/masks/__init__.py`, `masks/model.py`, `masks/candidates.py`, `masks/manifest.py`, `tests/unit/test_candidates.py`, `tests/integration/test_option_pool.py`, `scripts/analyze_mask_candidates.py`, and `docs/superpowers/evidence/task-9-mask-candidates.md`.

Public API extends the original conceptual interface with its missing corpus location:

`generate(families: FamilySet, revision: Revision, profile: Profile, *, project: Path, existing_masks: tuple[bytes,...] = ()) -> OptionPool`

Read references through `read_frame(project, frame_id)` once per unique reference. Verify revision/family/profile identity, selected occurrence mapping, native geometry/shades, domain completeness and manifest digest before checking candidates. Generated domain inputs retain synthetic provenance; validation sessions cannot fit new families. Incompatible covered inputs include every other frozen family's entire domain plus all observed corpus frames outside the chosen positive scope. No implicit omissions.

Create frozen dataclasses:

- `MaskOption(option_id: str, family_id: str, reference_frame_id: str, mask_id: str | None, ignore: bytes | None, crc32: int, shape: bool, positive_count: int, negative_count: int, domain_digest: str)`. `None` is unmasked and costs zero; custom IDs hash geometry and canonical bitmap bytes. Normalize an all-zero custom mask to None.
- `Rejection(family_id: str, mask_id: str | None, reason: str, input_digest: str | None, expected_crc: int | None, actual_crc: int | None, witness_pixels: bytes | None)`. Reasons distinguish positive variability, must-compare violation, invalid bitmap, equal compared bytes, CRC collision and invalid domain. Save one stable witness per rejection, never only an aggregate count.
- `OptionPool(schema_version: int, algorithm_version: str, revision_digest: str, family_digest: str, profile_sha256: str, scope_digest: str, generation_limits: tuple[int,int], options: tuple[MaskOption,...], rejections: tuple[Rejection,...], families_without_options: tuple[str,...], search_complete: bool, digest: str)`. Schema 1; algorithm `mask-candidates-v1`; generation limits `(256,64)` for pair/triple unions. `search_complete` means the declared generated pool was fully checked, never all mathematically possible masks.

`check_candidate(family: Family, reference: bytes, ignore: bytes | None, negatives: tuple[bytes,...], *, width: int, height: int, native_shades: int) -> MaskOption | Rejection` performs no I/O. For tiny synthetic geometries use a geometry-parameterized implementation of the same normal transform; the production Twister transform must agree byte-for-byte with Task 3's `compared_bytes`.

## Unit 1: Establish the complete candidate checker

- [ ] Write `test_positive_domain_invariance`: the candidate CRC must equal the reference CRC for every full positive domain frame, including held-out rendered values. Ignore all required positions, preserve all must-compare positions, and reject dimensions, shades, nonbinary masks and shape-enabled inputs.
- [ ] Write `test_cross_mask_crc_conflicts`: equal compared bytes from another family are rejected; independently constructed different bytes with an actual equal CRC32 are also rejected. Reuse Task 3's collision construction rather than mocking the CRC function. Test an incompatible frame belonging to a different mask, and brightness negatives outside ignored regions.
- [ ] Write `test_identical_contextual_inputs_have_no_discriminating_option`: conflicting expectations with the same native payload remain traceable and have no valid option; do not rely on rule ordering. All-hidden masks pass only if the incompatible input scope is empty.
- [ ] Run `uv run --group test pytest tests/unit/test_candidates.py -q`; observe failures attributable to the missing checker API.
- [ ] Implement the pure checker and strict input validation. Derive comparison bytes in raster order; remove ignored pixels and retain full native intensities. Check logical invariance as well as CRC invariance. Return the first deterministic failing input with full witness bytes and digests.
- [ ] Run the unit file and require every enabled assertion to pass. Record exact command/result in `.superpowers/sdd/2026-11-25-task-9-mask-candidates/progress.md`.

## Unit 2: Generate a bounded deterministic option pool

- [ ] Add fixtures for unmasked exact references, minimum-ignore masks, duplicate supplied masks, an existing useful bitmap and a zero-saving case. Test that one custom bitmap shared by two families has one mask ID but independent family options.
- [ ] Add `test_pairwise_sharing_does_not_validate_three_way_union`: construct independent expected results with at least one valid shared pair and a rejected three-family union. Preserve required-compare constraints and record the counterexample rather than accepting a compatibility graph as proof.
- [ ] Add `test_identity_and_domain_changes_invalidate_cache`: reject stale revision/profile/family digest, malformed or truncated domains, missing occurrence mappings and invalid cached results. Never fit the family from these negative inputs.
- [ ] Run the new tests and observe failures. Implement `generate`: try None, deduplicated supplied masks, and each family's required-ignore bitmap; build pair unions among unique nonempty seed masks in sorted mask-ID order, at most 256 pair unions. Add at most 64 three-seed unions from accepted pair seeds. Check each candidate independently against each eligible family and every incompatible covered input. Record the deterministic generation limits in the pool manifest.
- [ ] Optimize the common unmasked baseline with a single full-frame CRC index. For a custom mask, hash each unique covered input once and index conflicts by CRC, rather than doing a quadratic family-by-frame baseline scan. Use the mask applied to the negative input, regardless of that input's own prospective mask.
- [ ] Use an invocation-local cache keyed by revision, family/domain digest, bitmap, profile and algorithm; reuse only fully verified entries. Do not add a persistent cache in this task. Include negative-scope digest in each cache key.
- [ ] Report families with no options separately from rejected individual candidates. Never silently remove them from Task 10's required family list. Rerun focused tests and record results.

## Unit 3: Persist the pool and analyze the static corpus directly

- [ ] Write `test_option_pool_round_trip`: canonical save/reopen reproduces the typed pool and digest; reordered equivalent inputs produce identical bytes. Mutating a mask, witness, scope, domain or profile changes the digest. Rehashed semantic corruption (unknown family targets, inconsistent IDs, invalid bitmap or duplicate option IDs) fails validation.
- [ ] Implement `write_option_pool(pool: OptionPool, path: Path) -> None` and `read_option_pool(path: Path) -> OptionPool` in `masks/manifest.py`. Publish via sibling temporary file and atomic replacement. Save before/after identity checks and referenced family manifest beside the option pool so Task 10 can validate the handoff.
- [ ] Implement the direct CLI `scripts/analyze_mask_candidates.py --corpus PATH --output PATH`. Resolve the pinned profile using the existing profile APIs; locate a matching immutable revision through corpus metadata, recompute Task 7 coverage and produce/read the Task 8 exact-family manifest. If no corpus is available, a separate explicit `--dump PATH` mode imports the locked static file once into the run directory. Never invoke a local-dump pytest subprocess or installed application.
- [ ] Read and validate each unique native frame once. If the existing per-frame API repeatedly reads/checks whole chunk files, use a scoped verified chunk cache or bulk read helper with integrity checks and a bounded lifetime. Test this helper with generated data before running the real corpus; do not bypass checksums to save time.
- [ ] Run generated verification: `uv run --group test pytest tests/unit/test_candidates.py tests/integration/test_option_pool.py -q`. Observe a failing test before each implementation unit, then require green.
- [ ] Perform one direct real-data analysis using a reused corpus: `uv run --group test python scripts/analyze_mask_candidates.py --corpus <verified-corpus-path> --output artifacts/task9-<run-id>`. Save resolved paths/digests, elapsed time, counts, exit code, stdout/stderr, `families.json` and `options.json` to that directory. No additional real-dump test run is required.
- [ ] Reconcile 14,443 occurrences, 10,301 unique frames and 4,142 repeats with the static source provenance. Require every frozen family to have a valid option or an explicit no-option reason. A full-frame CRC collision may produce a no-option family; report it rather than asserting every frame must pass. Do not promise mask savings on the exact-only baseline.
- [ ] Run the full suite once after focused checks pass, retaining `--junitxml=artifacts/task9-<run-id>/suite.xml`. Confirm completed XML and exit code. Poll the actual running command only; if output stops, inspect the process tree/child CPU and artifact activity before diagnosing the cause. A waiting launcher alone is not evidence of an application prompt or a stalled analysis. Do not repeat a run solely because terminal output detached.
- [ ] Obtain one independent review; fix demonstrated correctness issues and rerun affected checks. Run `git diff --check`; record final evidence, source/corpus/family/pool hashes, scope limitations and Task 10 handoff paths. Synchronize plan/evidence to the main project's docs folders and leave changes uncommitted.

## Completion and execution budget

Complete when generated tests exercise all review-focus cases, direct static analysis produces a reopened identity-checked family manifest and option pool, all uncovered families have reasons, and final review/evidence is recorded. Native export/runtime replay and solver optimality are later gates. This task cannot declare completion from synthetic tests alone while its real-data handoff is missing.

Use one executor and one final review, three checkpoint entries and one real corpus analysis. Preserve the ledger with the last passing command and next unfinished step. Reuse all successful artifacts by digest. No ROM exploration, UI automation, native rebuilding, blanket full-suite repetition or separate static qualification process belongs in this plan.
