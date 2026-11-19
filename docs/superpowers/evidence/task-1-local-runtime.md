# Task 1 local runtime evidence

The Task 1 profile has two intentionally separate locks:

- **authoring**: ColorizingDMD and the bundled decoder at the pinned source-tree lock.
- **local-runtime**: VPinMAME64.dll, Bass64.dll, and serum64.dll staged for local runtime checks.

The profile's `file_version` fields are Windows VERSIONINFO numeric `a.b.c.d` values. Build labels such as PinMAME's `ecd032e` and Serum's product identity are recorded separately and are not substituted for a file version.

A passing local runtime check is not evidence that the editor's bundled decoder matches. The JSON output must show `authoring_binaries_verified: false` and `native_binaries_verified: false` unless the authoring scope is separately staged and passes.

## Reproduce

Set `DMD_LOCAL_RUNTIME=1`. Stage the declared local-runtime binaries exactly at:

```
artifacts/2026-11-18-task-1-fix-3/toolchain/pinmame/VPinMAME64.dll
artifacts/2026-11-18-task-1-fix-3/toolchain/pinmame/Bass64.dll
artifacts/2026-11-18-task-1-fix-3/toolchain/pinmame/serum64.dll
```

Then run:

```powershell
python -m pytest tests/integration/test_profile.py -q
python scripts/lock_profile.py --rom twst_405.zip --dump twst_405.txt --toolchain artifacts/2026-11-18-task-1-fix-3/toolchain --scope local-runtime
```

For a deliberate corruption check, copy the staged toolchain to a new folder, change one byte in `pinmame/serum64.dll`, and rerun the second command. It must fail with a SHA-256 mismatch. The locally gated `test_local_runtime_rejects_staged_serum_corruption` performs this corruption assertion when `DMD_LOCAL_RUNTIME=1`. Preserve the green and corrupt command output as Task 1 evidence.

To check authoring, stage `editor/ColorizingDMD.exe` and `editor/serum64.dll` at their independently pinned authoring digests, then use `--scope authoring`. Do not substitute the local VPinMAME serum DLL for this scope.
