# Task 8 Recognition Families Implementation Plan

> **For agentic workers:** Use superpowers:executing-plans inline, with one final independent review. Track the steps below. Leave changes uncommitted for the user's manual commit.

**Goal:** Freeze reproducible, evidence-backed recognition families for Task 9 while preserving exact references for every unsupported input.

**Architecture:** Read an immutable corpus and the Task 7 training-session selection. Start from exact native frames, discover candidate changes within captures, and accept dynamic groups only against an explicit finite field model. Freeze domains, pixel constraints, evidence and occurrence mappings into a hashed manifest; uncertainty never requires manual grouping approval.

**Tech Stack:** Existing Python standard library, SQLite corpus APIs, immutable dataclasses, canonical JSON and pytest. No new packages, native builds or application automation.

**Spec:** Task 8 of `docs/superpowers/plans/2026-11-18-dmd-mask-optimizer.md`; approved design sections 8, 9 and 18 in `DMD_Mask_Optimizer_Design_and_Implementation_Plan.md`; Task 7 handoff in `docs/superpowers/evidence/task-7-dump-coverage.md`.

## Global constraints

- Twister 4.05, 128 by 32, four native shades. Normal comparison only; ignore bit one internally. Preserve native shade differences, source pixels and all occurrences.
- Static qualification source: `C:\DMD Colorization\DMD Mask Optimizer V4\twst_405.txt`, SHA-256 `f711aec5d42fdc423ca02bfd2c8f05c158afaee27a97acdbf59d532b81095b11`.
- Reuse the immutable corpus capture created from that fixed source. Do not launch VPinMAME, ColorizingDMD, an interactive test harness, a dump recorder, or a separate application process to qualify Task 8. One direct source import per new corpus revision is sufficient.
- Expected observed input: 14,443 occurrences, 10,301 unique frames, 4,142 repeats. Task 7 reports supplied-dumps, observed-only, unknown reachable total and no independent validation sessions.
- Freeze established domains before mask selection. Never split an established family merely to lower the mask count. Task 9 owns CRC/mask feasibility and incompatible-family rejection.
- Existing colored projects are unnecessary. Do not write ColorizingDMD, VPinMAME, registry, source dump or existing output runs.
- Outputs belong in a fresh `artifacts/task8-<run-id>/` directory. Preserve user changes and leave all work uncommitted.
- Observations and shape similarity cannot prove unseen values. Synthetic model verification is distinguished from a proven connection to the ROM renderer. Do not claim exhaustive ROM coverage or independent real validation.

## Review focus

1. Similar digits in a static label, moving text, animation or another intensity state must not silently become an ignored field (Unit 2 negatives).
2. Correlated fields must use allowed joint values; independently combining their values invents unsupported inputs (Unit 2 domain tests).
3. Validation sessions must not influence proposals, glyph fitting, representatives or pixel constraints (Units 1 and 2 isolation tests).
4. Identical pixels can have different contextual expectations; visual deduplication must preserve the separate occurrence expectations (Units 1 and 3 mapping tests).
5. Unsupported rendering, excessive domains, stale identity and conflicting evidence must preserve exact fallbacks with reasons, without silently trimming an accepted domain (Units 2 and 3 rejection tests).

## Decisions and interfaces

The existing `Revision` holds counts and a digest but no corpus path or pixels. Extend the original conceptual API explicitly rather than inventing fields on it:

`infer(revision: Revision, evidence: Sequence[FieldEvidence], *, project: Path, coverage: CoverageReport) -> FamilySet`

The adapter checks revision counts/digest against `read_revision`, metadata ROM/profile identities against coverage, and selected session membership against corpus occurrences. It reads pixels through `read_frame`, once per unique selected frame. Session keys are `(capture_id, session)`; occurrence keys are `(capture_id, index)`. Reject overlapping training/validation keys, unknown sessions and stale coverage summaries. All corpus access remains read-only.

Create these frozen contracts in `families/model.py` (nested values must also be immutable):

- `OccurrenceKey(capture_id: str, index: int)` and `FrameSample(frame_id: str, pixels: bytes, occurrences: tuple[OccurrenceKey, ...])`.
- `FieldSpec(name: str, bounds: tuple[int,int,int,int], values: tuple[str,...], glyphs: tuple[tuple[str,bytes],...], glyph_width: int, glyph_height: int, advance: int, alignment: str, overflow: str)`. Bounds are `(x,y,width,height)`; native glyph shades, fixed advance, alignment `left|right`, overflow `reject|clip`. Signs, decimal separators, spaces and name characters are explicit glyphs and explicit value strings. No inferred numeric range endpoints or Cartesian products.
- `FieldEvidence(evidence_id: str, revision_digest: str, source_kind: str, source_digest: str, provenance: str, context: str, layout_id: str, animation_state: str, template_frame_id: str, fields: tuple[FieldSpec,...], joint_values: tuple[tuple[str,...],...], member_frame_ids: tuple[str,...], occurrence_keys: tuple[OccurrenceKey,...])`. Source kind is `synthetic-renderer` or `rom-renderer`; provenance identifies the independently checked source and its limitations. A ROM label alone does not establish that connection; unverified evidence is rejected with a reason. Context and layout/state are explicit expectation boundaries, not inferred from image similarity. Explicit occurrence keys bind contextual expectations; each key must belong to training scope and reference a claimed member frame. Conflicting claims for the same occurrence are unresolved.
- `Family(family_id: str, status: str, context: str, layout_id: str, animation_state: str, reference_frame_id: str, observed_frame_ids: tuple[str,...], domain_pixels: tuple[bytes,...], required_ignore: tuple[int,...], must_compare: tuple[int,...], evidence_ids: tuple[str,...], reason: str | None)`. Status is `established-finite`, `observed-only` or `uncertain-exact`. Domain pixels contain complete native frames, including generated variants, with their provenance in the manifest.
- `FamilySet(schema_version: int, algorithm_version: str, revision_digest: str, profile_sha256: str, families: tuple[Family,...], assignments: tuple[tuple[OccurrenceKey,str],...], unresolved: tuple[tuple[str,str],...], digest: str)`; algorithm `finite-families-v1`, schema 1. Assignment is per selected training occurrence, not just per unique frame.

`required_ignore` is exactly the positions that vary over the accepted full domain. `must_compare` is every other native pixel position, conservatively preserving fixed content for this first implementation. Sets must be disjoint and cover the geometry. A future relaxation must create a different family specification. Task 9 must not erase these retained positions.

Finite rendering uses the template's unchanged background, a zero native shade field background, explicit glyph bytes, alignment, advance and clipping. Require observed member pixels to equal a rendered allowed joint tuple exactly, including pixels outside fields. Reject overlapping fields, bad glyph dimensions/shades, unsupported characters and empty domains. A model that cannot reproduce the observations is unsupported; its inputs retain exact references. Different layout/state/context evidence never merges automatically.

Limit one proposed model to 4,096 joint tuples and 64 MiB of generated native pixels. If either bound would be exceeded, reject the proposal as `domain-budget-exceeded`, preserving exact fallbacks. Do not sample the domain and call it complete. Store deduplicated full rendered frames but retain the original allowed joint tuples and rendering specification in the frozen evidence. Larger renderer engines and extraction of ROM fonts/value sources are follow-up work, not a condition for an honest observed-scope result.

## Unit 1: Build the immutable exact-reference baseline

**Files:** Create `src/dmd_optimizer/families/__init__.py`, `families/model.py`, `families/infer.py`, and `tests/unit/test_families.py`.

**Consumes:** Task 5 `read_revision`, `read_capture_metadata`, `iter_occurrences`, `read_frame`; Task 7 `CoverageReport`.
**Produces:** The public `infer` signature and an exact FamilySet that covers selected training occurrences with no speculative merge.

- [ ] Add generated two-capture fixtures with repeats, a session reset and held-out sessions. Write `test_exact_baseline_preserves_occurrences`: each unique training payload has one exact reference in the default context, repeats map to it, all selected occurrence keys appear once and validation keys appear zero times.
- [ ] Write `test_stale_or_invalid_scope_rejected`: stale revision/profile, inconsistent coverage counts, unknown sessions and overlapping partitions fail with `FamilyError`. Inspecting a missing corpus creates no files.
- [ ] Run `uv run --group test pytest tests/unit/test_families.py -q`; confirm failure is caused by the missing family API.
- [ ] Implement immutable contracts, geometry validation, identity validation, deterministic reference choice and exact baseline. Reference choice is the lexicographically smallest observed frame ID in each family; family ordering is by family ID. Do not read validation frame payloads for fitting.
- [ ] Rerun the unit file and require all enabled assertions to pass. Record command and exit status in the run ledger.

## Unit 2: Verify finite dynamic fields and retain uncertain candidates

**Files:** Create `families/fields.py`, `families/proposals.py`; extend `families/infer.py` and `tests/unit/test_families.py`.

**Interfaces:** `render_domain(template: bytes, fields: tuple[FieldSpec,...], joint_values: tuple[tuple[str,...],...], *, width: int, height: int, native_shades: int) -> tuple[bytes,...]`; `propose(samples: tuple[FrameSample,...], *, width: int, height: int) -> tuple[tuple[str,str],...]` returns candidate frame pairs only, never accepted evidence.

- [ ] Write independently labeled tiny-geometry renderer fixtures: right/left aligned scores, value-width transition, punctuation/sign, clipped text and a small name alphabet. Reserve at least one allowed tuple from observed training pixels. Assert the accepted domain includes its independently rendered expected pixels without fitting glyphs or bounds from the holdout.
- [ ] Write negatives: static labels with digit-like shapes, sliding text, moving objects, animation changes and intensity changes outside fields remain separate. Unsupported movement is `uncertain-exact`; fixed position movement can be represented only through explicit separate layout/state specifications.
- [ ] Write `test_joint_fields_do_not_invent_combinations`: allowed tuples `(1,9)` and `(2,8)` do not admit `(1,8)`. Test unsupported glyphs, overlapping bounds, invalid evidence identity, conflicting models and the 4,096/64 MiB limits; each leaves exact fallbacks and a precise unresolved reason.
- [ ] Write `test_validation_never_changes_fitted_families`: modifying only held-out pixels or withheld labels cannot alter accepted training families. With a fixed matching revision fixture, compare semantic family specifications excluding input identity.
- [ ] Run the unit file; observe the new behavior fail before implementation.
- [ ] Implement finite rendering and complete domain checking. Accept a group only when all claimed observed members match and evidence passes identity/provenance checks. Conflicting evidence yields separate exact references, never order-dependent acceptance. Synthetic evidence remains identified as synthetic; Twister gets no invented ROM evidence.
- [ ] Implement cheap automatic proposals from adjacent distinct frames within each selected capture/session, using native pixel differences and their bounding rectangles. Never compare across resets. Emit pair/reason diagnostics for changing regions; no OCR or all-pairs scan. Unsupported proposals leave baseline assignments intact, so execution requires no manual grouping step.
- [ ] Compute exact required-ignore and must-compare sets over every accepted domain frame. Preserve context/layout/state boundaries. Rerun the focused unit tests and require all to pass.

## Unit 3: Freeze the manifest and prove the static Twister handoff

**Files:** Create `families/manifest.py`, `tests/integration/test_family_handoff.py`, and `docs/superpowers/evidence/task-8-recognition-families.md`.

**Interfaces:** `write_family_set(families: FamilySet, path: Path) -> None`; `read_family_set(path: Path) -> FamilySet`. Canonical UTF-8 JSON with sorted object keys and explicit ordering for unordered collections; SHA-256 excludes only the outer digest. Preserve semantic order for field tuples and glyph layouts. No run paths, timestamps or machine names in semantic IDs. Include full evidence and generated-domain provenance in hashed content.

- [ ] Write `test_frozen_manifest_is_reproducible`: repeat inference, reorder equivalent evidence input, save/reopen and compare the entire typed FamilySet and canonical bytes. Change one glyph, native shade, context or domain value and require a changed digest. Reject corrupt digest and unsupported schema/algorithm.
- [ ] Write `test_identical_pixels_keep_context_expectations`: explicit different contexts yield separate family IDs and traceable occurrence expectations. If context cannot be assigned uniquely from evidence, retain unresolved exact assignment rather than arbitrarily choosing. No occurrence disappears or receives two assignments.
- [ ] Run the new integration file and observe expected failure. Implement atomic sibling-temporary manifest publication, strict decoding, field/domain validation and digest checks. Verify complete assignment reconciliation against the selected training occurrences.
- [ ] Run one direct analysis against the immutable Task 6 corpus capture for the locked source. If a prior corpus artifact is unavailable, import `twst_405.txt` once with the Task 4/5 APIs into `artifacts/task8-<run-id>/corpus`, lock its digest, and reuse it for Task 7 coverage plus family inference. This is ordinary file analysis, not an application launch or a pytest-local qualification.
- [ ] Require 14,443 occurrences mapped, 10,301 exact visual references before contextual evidence, 4,142 repeats retained, zero speculative dynamic families, and unchanged source bytes. Report unresolved proposals and observed-only limitations. These are baseline counts, not promised mask savings.
- [ ] Demonstrate at least one useful dynamic family on the independent synthetic fixtures alongside the conservative Twister baseline. Record established/observed/uncertain counts separately; include revision/profile/source/family-set hashes and exact artifact paths for Task 9.
- [ ] Run synthetic verification only with `uv run --group test pytest tests/unit/test_families.py tests/integration/test_family_handoff.py -q`; save stdout, stderr and exit status beneath the fresh run folder. Record the direct-analysis result separately from pytest.
- [ ] Run the full project suite once after focused checks pass: `uv run --group test pytest -q`. Capture a machine-readable JUnit file with `--junitxml=artifacts/task8-<run-id>/suite.xml` so a detached Windows console does not force repeated full runs. Confirm the XML is complete, inspect failures/skips and record the process exit code; missing output is not success.
- [ ] Obtain one independent review of Task 8 source/tests and resolve demonstrated issues. Rerun only affected checks unless changes justify another full suite. Run `git diff --check`.
- [ ] Record results and scope in Task 8 evidence. Copy this plan and that evidence to the main project's matching `docs/superpowers` folders. Leave all changes uncommitted.

## Completion and efficiency

Task 8 is complete when exact fallback coverage is reconciled, finite synthetic models pass independent holdouts and negative cases, family specifications reopen with stable hashes, and the static Twister manifest is ready for Task 9. It does not require discovering a real Twister dynamic family without supporting evidence. Report that limitation explicitly; do not imply the synthetic cases prove Twister's numeric renderer.

## Execution record (2026-11-25)

The exact baseline, finite synthetic field models, canonical family manifest and
review hardening were implemented and verified. The final repository suite
passed 160 tests with 31 permitted skips. An attempted pytest-local Twister
qualification was withdrawn because it duplicated the direct immutable-import
workflow and wasted runtime. Future execution uses the single direct analysis
step above.

Use one executor, three recorded checkpoints (baseline, finite fields, manifest qualification) and one final review. Save progress in `.superpowers/sdd/2026-11-25-task-8-recognition-families/progress.md` with the last passing command and next unfinished step. Read pixels once per unique frame, use adjacent proposals rather than quadratic image comparisons, import the static dump at most once, and avoid repeating native/editor investigations. No Task 9 masks, solver, UI or export automation belongs in this task.
