# Task 6 ROM Audit and Capture Parity Evidence

**Status:** superseded. The optimizer will use VPinMAME's built-in text dumps,
not an independent same-run recorder. See
`docs/superpowers/plans/2026-11-25-task-6-vpinmame-dump-import.md`.

## Revised acquisition decision

The installed VPinMAME directory contains `dmddump\\twst_405.txt` and its
local documentation describes two supported ways to produce DMD dumps: create
the `DmdDump` directory and use F6 to record a game-named text file, or enable
`[rawoutput] enabled = true` in `DmdDevice.ini`. The latter was observed as
disabled; it was not changed. Both producer mechanisms write the source format
that Task 4's strict reader already consumes.

The optimizer will run after a user has selected completed files. It will not
run alongside PinMAME, modify VPinMAME configuration, monitor the folder, or
create a competing recorder. Multiple selected files become separate immutable
corpus captures under Task 5, retaining the origin and integrity hash of each.

The existing strict importer was run read-only against the installed
`C:\\vPinball\\VisualPinball\\VPinMAME\\dmddump\\twst_405.txt` and completed
all **15,291** records without a format error. Its identity is intentionally
kept separate from the earlier locked 14,443-record fixture: it is a different
user-produced capture, not a replacement for that fixture.

## Revised Task 6 qualification result

The selected VPinMAME dump was imported into the isolated worktree corpus at
`artifacts/task6-vpinmame-dump-corpus-final`. The resulting immutable revision
is `adef8406a191f4c6814572b991229ab5b89224f0d70cc04d74fbe3ead115c589`.
It contains one complete capture, **15,291** occurrence records, and **11,722**
unique native frames. Reopening the revision yielded all 15,291 occurrences;
the first stored frame was byte-for-byte equal to the first frame streamed from
the original VPinMAME text dump.

This qualifies the supported workflow of importing explicitly selected,
completed VPinMAME dump files. It does not claim full gameplay or ROM coverage.

## Locked inputs

- Profile: `twst_405`, driver `de_mSES1`, 128x32, native shades 0--3.
- Supplied ROM archive SHA-256: `7419195a51f1295e9f928e0105326cba3c4e32b9b2d3b59c004f773d132707a3`.
- Validated ROM content SHA-256: `8a2aff7218bdc969f9b53d93cfa6e926185e52e77abe4722c13ac511fbbb8035`.
- Pinned source: `ecd032e55481b261cce4820b53fd28fe478c70b4` in `artifacts/task6-pinned-pinmame`.
- Installed pinned runtime SHA-256: `69ebacabdb7e1af0533142a8456341f06e9d4b6cb3dc4649f18794be456ea8c1`.

## Native audit

`src/wpc/segames.c` declares the `twst_405` game entry. `src/wpc/se.c` selects
the `de_mSES1` hardware driver. `src/libpinmame/libpinmame.h` exposes
`PINMAME_DMD_MODE_RAW`; `src/libpinmame/libpinmame.cpp:431` is the raw display
delivery entry point.

The public `cb_OnDisplayUpdated` callback is not a qualification tap: its
implementation only calls the callback when its copied display buffer changes.
It would suppress a legitimate repeated native frame. A qualification worker
must therefore instrument the raw identification hook and the real consumer
handoff as separate writers before claiming parity.

## Build evidence

The exact source built with MSVC x64 Release and produced:

`vcproj/obj/VC2015/LibPinMAME/x64/Release/LibPinMAME64.dll`

MSBuild subsequently reports a failure only for the upstream project's obsolete
post-build copy destination `../../../UP2Dev/UP2Unity/`, which is absent in the
isolated worktree. The DLL and import library were already written. No installed
runtime or ColorizingDMD state was changed.

## Test evidence

- `python -m pytest tests/unit/test_rom_audit.py -q -p no:cacheprovider` -> 5 passed.
- `python -m pytest tests/unit/test_rom_audit.py tests/unit/test_live_capture.py -q -p no:cacheprovider` -> 12 passed.

## Bounded native smoke

The pinned source's sample client was rebuilt only inside
`artifacts/task6-pinned-pinmame`, with a bounded five-second `twst_405` run and
an owned `HOME/pinmame/roms` directory containing a copy of the supplied ROM.
It reached the raw DMD callback at 128x32/depth 2 and reported 231 frames at
59.21 FPS. The upstream sample returns `1` after `PinmameStop()`; it therefore
is not treated as a success signal or a qualification result. This proves the
pinned source can boot the selected ROM in isolated state, but not parity.

## Remaining completion gate

There is not yet an instrumented worker that writes separate same-run capture
and consumer traces, publishes a completion manifest, boots Twister from an
owned fresh-state directory, and imports the verified stream through Task 5.
Until that run passes, no support certificate exists and Task 6 is not complete.
