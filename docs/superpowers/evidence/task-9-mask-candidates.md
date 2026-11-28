# Task 9 Mask Candidate Evidence

## Static-corpus handoff

The locked source `twst_405.txt` was imported once into the worktree-local
corpus at `artifacts/task9-static-analysis-01/corpus`. No application,
VPinMAME session, recorder, watcher, or live intake was launched.

- Source SHA-256: `f711aec5d42fdc423ca02bfd2c8f05c158afaee27a97acdbf59d532b81095b11`
- Revision: `89a9cfd92f708b78be5e8d14feae3105058105b7af7a1606c16884c977e2b7c6`
- Counts: 14,443 occurrences; 10,301 unique frames; 4,142 repeats
- Families: 10,301 exact observed-only families; family digest `a8c7d730ac76a505f794b9886f49825a2a865b872c53117825ac0ae3efe1e84c`
- Options: 10,301 valid unmasked options; no families without options; pool digest `6a349ada6b3e2679c908c71bae58a81493dd762bbef42cbbae6fc7f180276657`

This exact-frame baseline proves reproducible option validity for the declared
observed scope. It does not claim mask savings; dynamic family evidence is a
later improvement to the frozen family input.

Focused verification: `uv run --group test pytest tests/unit/test_corpus.py::test_corpus_roundtrip_preserves_repeated_occurrences tests/unit/test_candidates.py tests/integration/test_option_pool.py -q`.
Result: **6 passed in 0.46 seconds**.

The published manifests were reopened and cross-checked: 10,301 families and
10,301 options, with the pool’s family digest matching the reopened family
manifest. Full-suite result: **196 passed, 31 skipped, 0 failures, 0 errors**
in 43.423 seconds; JUnit evidence is
`artifacts/task9-static-analysis-01/suite.xml`.

## Independent-review correction pass

The Task 9 review identified four correctness gaps. The correction pass now:

- validates pool family targets and revision/profile identity against the
  sibling immutable `families.json` handoff;
- canonicalizes family and mask-seed ordering before capped union generation;
- includes geometry in custom-mask IDs and preserves custom-mask IDs in
  rejection evidence; and
- validates declared family domains, pixel partitions, assignments, and every
  assigned stored corpus frame whenever a corpus project is supplied.

The regenerated handoff is `artifacts/task9-static-analysis-02/`, reusing the
immutable corpus from the first run. Its source/revision/family/pool digests
and counts match the first handoff. Focused correction tests: **9 passed**.
Full-suite correction verification: **199 passed, 31 skipped, 0 failures, 0
errors** in 33.530 seconds; JUnit evidence is
`artifacts/task9-static-analysis-02/suite.xml`.

Final completion verification reopened the same handoff under the stricter
family-target and bitmap validation rules. The remaining review-focus tests
now cover a real Task 3 CRC32 collision, identical contextual inputs, a
pairwise-valid but three-way-invalid union, and rehashed invalid/duplicate
manifest entries. Focused result: **12 passed**. Final suite: **202 passed,
31 skipped, 0 failures, 0 errors** in 51.245 seconds; JUnit evidence is
`artifacts/task9-static-analysis-02/suite-final.xml`.
