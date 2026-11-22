# Original-editor startup preflight

On November 20, 2026, the staged ColorizingDMD editor was still running at the 5,000 ms observation point. Windows reported visible top-level windows titled `ColorizingDMD`, `Backgrounds`, `Sprites`, and `Images`, plus a window titled with the staged executable path. The bridge then closed its kill-on-close job and waited for the process to exit. The next untested operation is deterministic project creation or import.

| Staged input | Read-only source | SHA-256 |
| --- | --- | --- |
| `ColorizingDMD.exe` | Locked editor installation at `C:\vPinball\ColorizingDMD` | `daf356ffae699ca830d6b2bdc3ffe2791908789f0d5671c2f8f448151b6caaa7` |
| `serum64.dll` | Separately retained source-tree Serum 2.1.0 DLL | `da71fa73e838ab3e257a2a73c8f74d88a3336615930761fa494a251822e0c2d5` |
| `textures/chiffres.raw` | `C:\DMD Colorization\ColorizingDMD\textures\chiffres.raw`, 1,815 bytes | `9eeea44b769035c9e49fe2fe90afa1463e047073384da0411c1c7e8e9a3f9a97` |

The first installation supplied the profile-declared dependency DLLs. The texture installation lacked `cargs64.dll`, `libcurl.dll`, and `sockpp64.dll`. Its `libserialport64.dll` and `zedmd64.dll` differed from the locked digests. The stage contained only the locked files. Decoder evidence identifies the bytes staged for launch. Runtime decoding remains untested.

The bridge acquired exclusive ownership and found no interrupted transaction. It journaled the settings subtree before applying six temporary directory values. After the child exited, the bridge compared a fresh enumeration against the snapshot, flushed the restored settings, and removed the marker. The real preflight test independently checked that the marker path was absent. The snapshot remains in the shared checkout's ignored journal.

The raw response is in `artifacts/startup-preflight-snh39h06/project-editor-config/bridge.stdout` in the task worktree. It records PID 4388, `running_at_deadline: true`, `editor_exited: true`, and `registry_transaction.verified: true`. The response uses the bridge's `startup-observation` failure stage because the project-writing interface requires an actual round-trip manifest for success. The generated project directory was empty after the observation. The real preflight test passed in 11.00 seconds.

## Job-wide shutdown verification

On November 22, 2026, the staged editor (PID 2792) remained active at 5,000 ms. Its main window identified ColorizingDMD v3.17.1 and displayed frame and session counters. Windows also reported the Images, Sprites and Backgrounds windows. The bridge terminated the job, observed zero active processes out of two total, and confirmed that the main process handle had signaled. The registry comparison passed and the incomplete marker was absent. The final acceptance test passed in 6.78 seconds. Its response is in `artifacts/startup-preflight-gxx208ua/project-editor-config/bridge.stdout`.

An earlier run observed zero active job members before the main process handle signaled. The bridge retained its marker. A recovery-only invocation verified restoration and removed the marker. The final bridge waits for the main process using the remaining time in the same five-second cleanup deadline. Under exclusive ownership, recovery of a previously journaled transaction precedes validation of the next request. A fresh transaction requires validated assets and a second check for a running editor.
