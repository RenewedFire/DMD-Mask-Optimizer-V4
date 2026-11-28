# Task 13 desktop authoring workflow evidence

Qualification uses generated Qt fixtures and the fixed static Twister corpus rule only. It does not launch ColorizingDMD, VPinMAME, a recorder, a folder watcher, or an editor bridge.

`python scripts/launch_desktop.py --check` reports PySide6 availability, the local fixed-corpus status, the `twst_405` profile, and `external_apps_required: false` without opening a window.

The desktop tests cover background progress, cancellation, single-job enforcement, failure visibility, ROM/dump path validation, 1,800-second defaulting, safe diagnostic-only output actions, and nearest-neighbor four-shade previews.
