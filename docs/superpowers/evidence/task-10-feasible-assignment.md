# Task 10 — Feasible assignment evidence

## Scope and immutable input

This task consumed the verified Task 9 handoff only:

- pool: `artifacts/task9-static-analysis-02/options.json`
- family manifest: `artifacts/task9-static-analysis-02/families.json`
- pool digest: `6a349ada6b3e2679c908c71bae58a81493dd762bbef42cbbae6fc7f180276657`
- family digest: `a8c7d730ac76a505f794b9886f49825a2a865b872c53117825ac0ae3efe1e84c`

No source-dump import, VPinMAME process, ColorizingDMD process, recorder, watcher, or live folder intake was used.

## Solver contract

`mask-cover-v1` is implemented with OR-Tools CP-SAT `9.15.6755`.  It selects exactly one Task 9 option per frozen family, charges once for each distinct non-null custom mask ID, and enforces the Twister cap of 64 custom masks.  Saved solutions bind their pool, family, revision, profile, scope, and model identities and are atomically written.

Focused command:

```text
uv run --group test pytest tests/unit/test_solver.py tests/integration/test_solve_handoff.py -q
```

Result: `8 passed` (exit 0).  The tests cover shared-mask counting, unmasked selections, missing options, cap infeasibility, rehashed proof/infeasibility tampering, model identity mismatch, deterministic option-ID tie-breaking, cancellation-before-solve, zero-time behavior, and persistence/profile validation.

## Static Twister result

Command:

```text
uv run --group test python scripts/solve_mask_assignment.py --pool artifacts/task9-static-analysis-02/options.json --output artifacts/task10-static-solve-02 --time-limit-seconds 30
```

Published files:

- `artifacts/task10-static-solve-02/solution.json`
- `artifacts/task10-static-solve-02/summary.json`

Result summary:

| Field | Value |
| --- | --- |
| status | `optimal-pool` |
| assignments | 10,301 / 10,301 frozen families |
| active custom masks | 0 / 64 |
| proven lower bound | 0 |
| bound scope | `candidate-pool` |
| solution digest | `781c110865b70453e305ac21dfefb2f74a23e7d0b40e8a8b891a75dc68121e8a` |

This proves the zero-custom-mask result only for the exact observed Task 9 candidate pool and frozen family scope.  It does not claim ROM-wide coverage, editor exportability, or native rendering equivalence; Task 11 owns those checks.

## Independent review resolution

An independent review identified insufficient bound validation, certificate-less persisted infeasibility, cancellation coverage, and missing deterministic tie-breaking.  The resolved implementation requires `optimal-pool.lower_bound` to equal the selected count, rejects persisted `infeasible-pool` results without an external UNSAT certificate, supplies deterministic greedy hints, and uses option-ID rank only after the primary mask-count objective.  The focused tests above were rerun after those fixes.
