# Task 7 Dump Coverage Evidence

## Fixed input

The qualification input is the static project file
`C:\\DMD Colorization\\DMD Mask Optimizer V4\\twst_405.txt`.
Its SHA-256 is
`f711aec5d42fdc423ca02bfd2c8f05c158afaee27a97acdbf59d532b81095b11`.

## Observed scope

The immutable corpus contains 14,443 occurrences, 10,301 unique native frames,
and 4,142 repeated occurrences. Its sole observed session begins at tick
`0x00088b41` and ends at `0x00227c3f`. The report records this as
`observed-only`: the total reachable output count is unknown, and there is no
independent validation capture.

The saved obligations are: reachable output domain unproved; language/settings
domain unknown; initial state domain unknown; gameplay-mode coverage unproved;
independent validation capture missing; and timestamp unit unknown.

## Verification

The Task 7 coverage tests exercise corpus-provenance scoping, repeated-frame
counting, cancellation/resume, checksum-protected checkpoint corruption, and
revision mismatch rejection. The local qualification reads the fixed project
dump, confirms its hash and frame/tick counts, and compares a resumed report
with an uninterrupted report.

Final command:

```powershell
$env:PYTHONPATH = 'artifacts\task3-test-deps;src;.'
$env:DMD_TWISTER_DUMP = 'C:\DMD Colorization\DMD Mask Optimizer V4\twst_405.txt'
& 'C:\DMD Colorization\DMD Mask Optimizer V4\.venv\Scripts\python.exe' -m pytest -q -p no:cacheprovider --basetemp=artifacts\task7-full
```

Result: **154 passed, 27 skipped in 377.55 seconds**.

## Post-review checkpoint hardening

The final independent review identified four issues in the initial implementation.
The follow-up uses SQLite read-only connections for coverage inspection,
reconstructs and compares every checkpoint prefix including ordinal zero,
continues from that reconstructed state to retain corpus session order, and
streams occurrences rather than buffering the complete capture.

Post-review regression verification:

```powershell
uv run --group test pytest tests/unit/test_coverage.py tests/integration/test_exploration.py -q
```

Result: **7 passed in 2.92 seconds**. The local Twister qualification was
rerun with `DMD_TWISTER_DUMP` set to the fixed source. A subsequent full
`uv run --group test pytest -q` completed; this Windows terminal bridge
detaches long-lived `uv` children and did not retain pytest's summary, but the
refreshed `lastfailed` cache was `{}`. The fully captured 154/27 result above
remains the recorded complete-suite result from initial qualification.

## Task 8 handoff

Task 8 receives the immutable revision selected by the caller and the ordered
training session keys `(capture_id, session)` in `CoverageReport`. It receives
no validation session for this build. Family conclusions may only claim the
observed dump scope; wider gameplay and configuration domains remain provisional.
