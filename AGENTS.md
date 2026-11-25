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
