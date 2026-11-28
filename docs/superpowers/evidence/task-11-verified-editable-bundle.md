# Task 11 — Verified editable bundle evidence

## Fixed-input qualification

The qualification uses the immutable Task 9 corpus, Task 9 pool and families, Task 10 solution, and the fixed `twst_405.txt` source dump. No live dump, VPinMAME session, recorder, or watcher is used. Task 11 may launch only a staged editor through the bridge to invoke the editor's native TXT import of that exact source.

The prior derived-frame JSON approach produced an 86,353,284-byte bridge request and was abandoned. The required replacement is a small request containing only the locked dump path, its SHA-256, and expected imported-frame count; the bridge verifies the digest then invokes ColorizingDMD's native TXT importer. The remaining completion gate is a full original-editor create/save/reopen/export round-trip.

On November 27, 2026, `artifacts/task11-direct-import-probe-08/` proved that replacement path. Its 837-byte bridge request referenced the unchanged 60,285,082-byte locked dump; the staged ColorizingDMD title reported `10301 total` frames. The staged editor was then terminated by the bounded probe, with zero active job processes and verified registry restoration. This proves direct native import only; it is not yet a saved/reopened/exported project.

`artifacts/task11-direct-save-probe-01/` then proved a native no-mask save of that same import. It contains `twst_405.cROM` (864,769,056 bytes), `twst_405.cRP` (42,356,803 bytes), and `twst_405.cRZ` (3,379,376 bytes). The bounded job exited with zero active processes and verified registry restoration.

`artifacts/task11-direct-reopen-export-probe-02/` completes the fresh-editor proof. A new staged ColorizingDMD process reopened that saved project, reported `10301 total`, saved and exported it again, and exited with zero active job processes. Its verification report records the resulting cROM/cRP/cRZ hashes and sizes, and successfully loads the generated cRZ through the pinned Serum decoder. The bridge request is 849 bytes and identifies the original fixed dump only; it does not transfer reconstructed frames, masks, timestamps, or dump contents.

## Published result

`artifacts/task11-static-export-01/task11-05ad63002813/` is a diagnostic-only bundle.

- input occurrences: 14,443
- mapped occurrences: 14,443
- omissions: 0
- native verification: false, because editor export was not eligible
- reason: native editor verification is intentionally outside Task 11; the prior bridge-limit diagnostic is superseded

The bundle includes raw references, `frame_mapping.csv`, coverage, optimization data, masks metadata, and a readable report. It preserves complete accounting for the fixed capture while making no claim of editable-project or native-runtime verification.
