# Task 10 Feasible Assignment Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task by task. Steps use checkbox (`- [ ]`) syntax for tracking. Leave changes uncommitted for the user's manual commit.

**Goal:** Select one verified Task 9 option per frozen family while minimizing the number of distinct active custom bitmaps, enforcing the pinned 64-slot mask limit, and reporting only bounds proved for that exact pool and scope.

**Architecture:** Load the immutable Task 9 pool beside its family manifest, validate the handoff, obtain a deterministic feasible incumbent, then solve a shared-mask activation model. Save an identity-bound result for Task 11 to verify against exported native artifacts. The observed-only exact Twister baseline is expected to choose 10,301 unmasked options at cost zero; that is a pool optimum, not proof of full ROM coverage or an all-mask optimum.

**Tech Stack:** Python 3.11+, pytest, canonical JSON, OR-Tools CP-SAT pinned in `pyproject.toml`/`uv.lock` during implementation.

**Spec:** `DMD_Mask_Optimizer_Design_and_Implementation_Plan.md` §§2, 4, 10–11; `docs/superpowers/plans/2026-11-18-dmd-mask-optimizer.md` Task 10; `docs/superpowers/plans/2026-11-25-task-9-mask-candidates.md`; `AGENTS.md`.

## Global Constraints

- Reuse `artifacts/task9-static-analysis-01/corpus` and the verified `artifacts/task9-static-analysis-02/families.json` and `options.json`. The pinned source is `C:\DMD Colorization\DMD Mask Optimizer V4\twst_405.txt`, SHA-256 `f711aec5d42fdc423ca02bfd2c8f05c158afaee27a97acdbf59d532b81095b11`. Do not re-import it unless the immutable corpus is unusable.
- No VPinMAME, ColorizingDMD, recorder, watcher, interactive qualification, or live source intake. Use direct corpus analysis and ordinary tests.
- Freeze families and their full domains. Do not omit a required family or relax Task 9 validity to obtain a solution. Preserve `families_without_options` as an explicit infeasibility reason.
- Normal comparison only; no shape mode. Distinct active custom bitmap IDs cost one each; unmasked options cost zero. Pin the original editor's custom-mask cap to 64 for the Twister profile; fail closed on an unsupported profile.
- Objective order: custom mask count, then redundant reference count, then measured runtime cost. Only optimize a secondary objective after fixing the proven primary value. If the last two metrics cannot be measured defensibly from the available pool, retain stable deterministic tie-breaking and report them as unavailable rather than inventing savings.
- A lower bound, optimality status, and model digest apply only to the exact Task 9 option pool, frozen family scope, comparison policy, and cap. Task 11 owns native export verification and reference/format limits; Task 10 must not claim a publishable project.

## Review Focus

1. Two families using the same bitmap activate one mask, while two different bitmap IDs cost two; test independent enumeration on a tiny pool.
2. A family with no options or a mask count above 64 is infeasible for the full frozen scope; test both without silently dropping families.
3. Solver timeout or cancellation with an incumbent is feasible but unproved; without one it is unknown. Test both and ensure no false optimum.
4. An old pool, family digest, profile, model version, or scope cannot validate a saved solution; test each mismatch and tampering.
5. A restricted candidate pool can have a worse optimum than unrestricted bitmaps; test that its reported bound remains pool-scoped.

---

### Task 1: Define and validate the solve contract

**Files:** Create `src/dmd_optimizer/solve/__init__.py`, `src/dmd_optimizer/solve/model.py`, `src/dmd_optimizer/solve/manifest.py`, `tests/unit/test_solver.py`.

**Interfaces:** Consumes `OptionPool`, `MaskOption`, and the sibling Task 8 `FamilySet`. Produces frozen `SolveResult(schema_version, algorithm_version, pool_digest, family_digest, revision_digest, profile_sha256, scope_digest, model_digest, assignment: tuple[tuple[str,str],...], selected_mask_ids: tuple[str,...], selected_mask_count: int | None, lower_bound: int | None, bound_scope: str, status: str, stop_reason: str | None, digest: str)` and `validate_result(result, pool, families, *, mask_cap: int) -> None`. Status vocabulary: `optimal-pool`, `feasible-unproved`, `infeasible-pool`, `no-feasible-option`, `unknown`.

- [ ] **Step 1: Write failing tests.** Assert a shared bitmap counts once, unmasked costs zero, assignments contain exactly one listed option per family, selected mask IDs equal the unique non-null IDs, and a missing family is never silently omitted. Test mismatched pool/family/profile/scope, inconsistent bitmap ID, duplicate assignment, and rehashed corruption.
- [ ] **Step 2: Run** `uv run --group test pytest tests/unit/test_solver.py -q`. **Expected:** failure because the solve contract module is missing.
- [ ] **Step 3: Implement** the frozen result contract and validator. Canonical SHA-256 must cover all semantic fields except `digest`. Validate the Task 9 family manifest and every chosen option ID; a result with no assignment may represent only an explicit infeasible/unknown status.
- [ ] **Step 4: Run** the same focused command. **Expected:** all Task 1 tests pass.
- [ ] **Step 5: Record** exact command, result, and any design ruling in `.superpowers/sdd/2026-11-25-task-10-feasible-assignment/progress.md`.

### Task 2: Find a feasible assignment and a scoped optimum

**Files:** Create `src/dmd_optimizer/solve/cover.py`; extend `tests/unit/test_solver.py`; modify `pyproject.toml` and `uv.lock` to pin the tested OR-Tools version.

**Interfaces:** `solve(pool: OptionPool, profile: Profile, stop: StopToken, *, families: FamilySet, time_limit_seconds: float) -> SolveResult`. `StopToken` exposes `stopped() -> bool`; define a trivial never-stop implementation for the CLI. Return statuses and bounds from Task 1.

- [ ] **Step 1: Write failing generated tests.** Independently enumerate tiny assignments and bitmaps to establish the pool optimum. Assert a shared-mask optimum of two, a zero-cost unmasked baseline, a case whose pool optimum exceeds an unrestricted bitmap minimum, a >64-mask infeasible pool, and no-option family. Simulate stop and time limit with/without an incumbent. Assert deterministic assignment and correct bound scope.
- [ ] **Step 2: Run** `uv run --group test pytest tests/unit/test_solver.py -q`. **Expected:** missing `solve` or failing objective/status cases.
- [ ] **Step 3: Implement** deterministic greedy incumbent first. Build CP-SAT Boolean option-choice variables (exactly one per family) and bitmap-activation variables (choice implies activation), cap activation sum at 64, and minimize activation sum. Supply the incumbent as hints. Never infer infeasibility from a timeout. Use solver `OPTIMAL` and `INFEASIBLE` only for a complete model; use `BestObjectiveBound` only when valid for the same model, rounded safely down to an integer lower bound. Fix the primary optimum before any defensible secondary optimization; otherwise use sorted option IDs as stable tie-break. Revalidate every candidate result with Task 1's validator before returning it.
- [ ] **Step 4: Run** the focused test file. **Expected:** all generated cases pass and computed bounds agree with independent enumeration.
- [ ] **Step 5: Record** the solver version, focused result, scope of the bound, and timeout behavior in the ledger.

### Task 3: Persist and qualify the existing Twister pool

**Files:** Complete `src/dmd_optimizer/solve/manifest.py`; create `scripts/solve_mask_assignment.py`, `tests/integration/test_solve_handoff.py`, `docs/superpowers/evidence/task-10-feasible-assignment.md`.

**Interfaces:** `write_solve_result(result: SolveResult, path: Path) -> None`, `read_solve_result(path: Path, *, pool_path: Path, profile: Profile) -> SolveResult`. CLI: `--pool PATH --output PATH --time-limit-seconds N`, loading sibling `families.json`, pinned profile and Task 9 pool. Output under fresh `artifacts/task10-<run-id>/` with result JSON and summary.

- [ ] **Step 1: Write failing integration tests.** Round-trip typed result and digest; reject altered option, scope, pool, family/profile or model digest even if result JSON was rehashed. Verify cancellation/timeout result remains reopenable. Confirm the CLI never reads the source dump when given the existing pool.
- [ ] **Step 2: Run** `uv run --group test pytest tests/unit/test_solver.py tests/integration/test_solve_handoff.py -q`. **Expected:** failure from missing persistence/CLI behavior.
- [ ] **Step 3: Implement** atomic sibling-temp-file publication and read-back validation. Reject stale or unsupported profiles; report the 64-mask cap as the active limit. Save the pool/family/revision/profile/model identity and proof scope alongside the solution; preserve a candidate result separately until validation and read-back pass.
- [ ] **Step 4: Run** the focused command. **Expected:** all tests pass.
- [ ] **Step 5: Run direct analysis** against `artifacts/task9-static-analysis-02/options.json`; write one fresh Task 10 artifact directory. Check source/revision/profile/family/pool digests, 10,301 required families, exactly one assignment each, zero active masks and a pool optimum lower bound of zero. If the cap or reference format prevents Task 11 publication, report it as a downstream export limitation rather than altering the family scope.
- [ ] **Step 6: Run** `uv run --group test pytest -q --junitxml=artifacts/task10-<run-id>/suite.xml`, then `git diff --check`. **Expected:** zero failures/errors and a completed XML report.
- [ ] **Step 7: Obtain one independent review, fix demonstrated correctness defects, and rerun affected tests.** Record commands, exit codes, elapsed time, hashes, optimizer version, statuses and limits in the evidence and ledger. Synchronize plan/evidence to the main project's `docs/superpowers/` folders. Leave all code and docs uncommitted for manual review.

## Completion

Task 10 is complete only when the saved solution reopens against the exact Task 9 pool and family manifest, all required families have one option, distinct mask cost/cap and statuses are verified by independent tiny-case enumeration, the static Twister baseline has a scoped result, the full suite passes, and the independent review is resolved. Task 11 separately checks exportability and native matching.
