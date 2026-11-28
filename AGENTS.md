# Project instructions

## Static dump analysis rule

The fixed project dump `twst_405.txt` is the canonical input for this build.
Every future implementation plan and execution step must reuse its immutable
corpus capture, or create one worktree-local immutable import only when that
capture is unavailable.

Do not plan or run a separate interactive qualification process, application
launch, VPinMAME session, ColorizingDMD session, dump recorder, folder watcher,
or live-source intake to analyze this build's static dump. Use direct corpus
analysis and ordinary unit/integration tests instead. Any later change to this
rule requires an explicit user decision and a new locked input revision.

## ColorizingDMD import boundary

The optimizer must never reconstruct or serialize `twst_405.txt` into derived
per-frame JSON, regenerated timestamps, or a replacement dump. Task 11 may use
the native editor bridge solely as a staged-editor launcher and isolation wrapper
to give ColorizingDMD the original locked TXT path through its normal native
TXT-import workflow. That preserves timestamps and the application's own
duplicate-frame handling. The optimizer consumes the same fixed dump/corpus for
direct static analysis and produces companion mappings, masks, and reports.

The editor bridge is not a production data transport or project writer. Its only
permitted fixed-dump role is Task 11's explicitly approved staged launch of the
editor's own TXT importer. It must pass only the original absolute dump path,
its SHA-256, and expected native imported-frame count; it must never receive
frame pixels, masks, synthetic timestamps, or a dump payload.
