# Task 8 Recognition Families Evidence

## Scope

Task 8 freezes exact visual families and accepts a dynamic family only when a
finite, explicit field model reproduces every claimed observed member. The
Twister input has no renderer evidence in this build, so its baseline remains
observed-only exact references. The synthetic fixtures demonstrate the
finite-field mechanism without claiming a connection to Twister rendering.

## Qualification input

`C:\DMD Colorization\DMD Mask Optimizer V4\twst_405.txt`

SHA-256: `f711aec5d42fdc423ca02bfd2c8f05c158afaee27a97acdbf59d532b81095b11`.

## Task 9 handoff

The family manifest contains immutable family IDs, per-occurrence assignments,
observed source frame IDs, required-ignore pixels, retained must-compare
pixels, evidence IDs and unresolved reasons. Task 9 may create candidates only
within a frozen manifest's stated domain. It must keep all observed-only
families as exact references unless later evidence revises the family set.

## Verification

Focused family and manifest checks after final review:

```powershell
uv run --group test pytest tests/unit/test_families.py tests/integration/test_family_handoff.py -q
```

Result: **6 passed in 1.95 seconds**.

The final repository suite was run non-interactively with JUnit output at
`artifacts/task8-suite/final-suite.xml`: **160 passed, 31 skipped in 41.19
seconds**, with zero failures and errors.

An attempted pytest-local Twister qualification was stopped after its child
waited for console input. That process was unnecessary: Task 6 already defines
the fixed project dump as the canonical immutable input, and the intended
workflow is one direct corpus import followed by analysis. Future Task 8 and
later-task execution must reuse that import or make one new worktree-local
import when the artifact is absent. They must not start VPinMAME, ColorizingDMD
or a separate interactive qualification process.

## Final review remediation

Independent review fixes added ROM identity validation, strict training-scope
membership for evidence frames, a verified provenance requirement for
ROM-renderer evidence, complete finite-domain limits, and manifest validation
for family IDs, assignments and pixel partitions. Unsupported evidence remains
an explicit unresolved exact fallback.
