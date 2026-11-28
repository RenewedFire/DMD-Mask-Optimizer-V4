# Task 5 corpus-store evidence

## Scope

The store is local to its supplied project directory. This task wrote its Twister qualification corpus only below `artifacts/task5-twister-background/`; it did not write to either installed ColorizingDMD directory or modify a ROM/dump.

## Verification

Focused synthetic and real qualification (with `DMD_TWISTER_DUMP` set to the locked `twst_405.txt`):

```text
python -m pytest tests/local/test_twister_corpus.py -q -p no:cacheprovider --basetemp=artifacts/task5-twister-background
1 passed in 39.29s
```

The locked dump SHA-256 was verified before import. The import produced 14,443 ordered occurrences, 10,301 unique frames, and 4,142 repeated frames. First/last ticks were `0x00088b41` / `0x00227c3f`; the final duration status was `final-unknown`. Reimport returned the same revision digest without adding a capture. The final run passed in 39.15 seconds. Its importing Python process peaked at 106,909,696 bytes (about 102 MiB); this includes pytest and verification objects, so it is a conservative upper bound rather than store-only memory.

- Revision: `a48ced6c1552f3be5b4bfa6a0534d117eaa4c30282feca30d46429c8a1c88b04`
- Chunks: 11, 42,234,166 bytes total; largest 4,198,406 bytes.

```text
python -m pytest tests/unit/test_corpus.py -q -p no:cacheprovider --basetemp=artifacts/task5-unit-chunked2
5 passed in 0.51s

PYTHONPATH=artifacts/task3-test-deps;src;. python -m pytest -q -p no:cacheprovider --basetemp=artifacts/task5-full-fixed
132 passed, 29 skipped in 22.92s
```

The full-suite background launcher did not propagate the optional dump variable; the focused command above is the real-fixture certification.

## Format and recovery

Chunks use `DMDC1\\0` and big-endian length-prefixed native-u8 records. SQLite stores per-chunk SHA-256 and record bounds. Frame identity is SHA-512 of canonical geometry/encoding metadata plus raw bytes; SHA-256 is only a non-unique lookup bucket.

`recover()` locks the store, validates SQLite and all referenced chunks, then moves only unreferenced store-owned staging/chunk files to `orphans/<run-id>/`. The unit qualification created an unreferenced `chunks/orphan.bin` and confirmed it was quarantined, then removed a referenced chunk and confirmed recovery raised `CorpusError`. It never deletes data. Missing or corrupt referenced chunks raise `CorpusError`.
