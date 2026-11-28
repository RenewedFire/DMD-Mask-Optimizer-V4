# Task 12 — Bounded jobs and recovery evidence

## Fixed-input qualification

`artifacts/task12-bounded-job-01/run-6a1e34d00fe1/` is a one-second controller qualification. It read the immutable Task 9 corpus database and Task 10 solution manifest only. No VPinMAME process, ColorizingDMD editor, recorder, watcher, or live input process was started.

- corpus SHA-256: `f3afdf93beed03da7945f13d0a86a4dafaa5115c8db9f973645469f2c29a994b`
- solution SHA-256: `3b428ea87c4275e0d8cb0594946e8dcd61835ec31655241d46df19bb59b38bcf`
- checkpoint digest: `4fe8c18f47bb64489c27f36920b1bc519ad970d747c48ed532c42c34cef10fd3`
- stop reason: `completed`; processing time: 0.007860 seconds; flush time: 0 seconds
- export status: `diagnostic-only`; no native publication or new editable-project claim was made

The controller tests cover checkpoint fallback after corruption, deadline and cancellation behavior, worker failure, late pending frames, fresh run directories, finalization-time reserve, and compatible versus stale resume identity. The full Python suite passed with 208 tests and 32 skipped tests after Task 12 implementation.
