# Task 2 — Original Editor Round-Trip Design

## Intent

Prove that the optimizer can create a minimal, editable Twister project that
the installed original ColorizingDMD editor opens, saves, exports, and reopens
without changing the source-reference pixels or mask assignments that matter
to later matching work.

## Context

Task 1 locks the Twister fixture at 128×32 with four native shades and records
the local ColorizingDMD installation at `C:\vPinball\ColorizingDMD`. Its
`formats.txt` is explicitly historical guidance, not a version-specific
serializer contract. The installed directory contains existing Twister project
files (`.cROM`, `.cRP`, `.cRZ`, and optional `auto` output), so discovery can
use them read-only as format witnesses.

## Goals

- Use the installed original ColorizingDMD executable as the serialization and
  loading authority.
- Create a generated three-reference fixture: two references share one custom
  comparison bitmap and the third has no comparison bitmap.
- Preserve stable IDs, source/native pixels, reference order, normal comparison
  mode, mask sharing, and hidden pixels through create → open → save → reopen →
  export.
- Record actual companion-file names, headers, field widths, endianness,
  defaults, and the verified 64-slot / sentinel-255 limits.
- Retain a small generated golden package and binary fingerprints as evidence.

## Non-goals

- Do not alter the user's existing projects or source installation.
- Do not treat `formats.txt` as sufficient proof of the selected build's format.
- Do not certify matching behavior; that belongs to Task 3's native oracle.
- Do not build a general standalone project serializer in Task 2.

## Approaches

1. **Editor automation bridge — chosen.** A Windows-only bridge drives the
   pinned executable in an isolated generated directory and observes its
   persisted outputs. A Python adapter exposes a stable typed interface to the
   rest of the optimizer. This is the only approach that directly proves
   editability in the selected original editor.
2. **Standalone writer plus editor validation.** A writer would infer the
   format from samples and validate its output in the editor. It is deferred:
   the supplied format description is known to be older than the selected
   build, and independent serialization would introduce avoidable format risk.

## Design

`native/editor_bridge.cpp` is a narrow Windows x64 executable. Before every
run, it stages an isolated editor tree that contains the pinned
`ColorizingDMD.exe` plus the exact source-tree decoder DLL locked by Task 1
(`sha256 da71fa73e838ab3e257a2a73c8f74d88a3336615930761fa494a251822e0c2d5`,
version 2.1.0) and its declared editor dependencies. It rejects a missing or
mismatched file. In particular, it must not silently use the installed
`C:\vPinball\ColorizingDMD\serum64.dll` or the separate local-runtime Serum
2.5.2 fixture. It accepts a versioned JSON request that names a sandboxed
project directory and a generated reference fixture; it never targets
`C:\vPinball\ColorizingDMD\Projects`. It launches the staged editor, performs
the smallest deterministic interaction needed to create/open/save/export the
fixture, and returns a manifest of files and observations. It must fail with
an actionable editor/process/timeout diagnostic rather than fabricate a
project.

`src/dmd_optimizer/adapters/editor.py` owns the Python-facing types:
`Reference`, `ProjectFiles`, and `write_project(folder, refs, profile)`. It
validates Task 1 geometry/shades, serializes the bridge request, records the
bridge manifest, and offers reopen/export inspection used by integration tests.

The bridge test fixture has exactly three distinct 128×32 row-major native
pixel frames with shades 0–3. `Reference` IDs are unique and nonempty; their
optional same-sized binary comparison bitmap uses `1 = ignore`, and all three
use `shape=false`. References A and B have distinct source pixels even after
their shared nontrivial bitmap is applied; reference C is unmasked. The test
assigns ordinary grayscale palettes and keeps at least one hidden pixel so
source-pixel preservation is observable. Since the editor format may not
persist optimizer IDs, the bridge writes a manifest sidecar mapping each input
ID to reopened ordinal, source-pixel digest, and slot assignment.

The bridge records the editor-generated slot assignment and unmasked sentinel.
Task 2 proves the observed sentinel is 255 and runs a separate 64/65 custom
bitmap boundary probe: 64 distinct masks must save/reopen; adding a 65th must
be rejected or produce an explicit observed editor-limit diagnostic.

The controlled operation sequence is bounded: create/import → assign masks →
open → fresh save → new-process reopen → export. The bridge redirects writable
editor configuration, autosave, and project paths into its sandbox. If the GUI
cannot perform that sequence deterministically, it stops with evidence; it
does not replace the editor with a direct writer.

Run packages, screenshots/logs, binary fingerprints, and schema observations
live under `artifacts/<run-id>/` and remain ignored by Git. The compact
synthetic golden package is tracked under
`tests/fixtures/editor_roundtrip/golden/`; it contains no supplied ROM or
capture. The adapter receives the explicitly staged editor root in its test
harness and reuses the Task 1 component-verification logic without requiring
the private ROM/dump inputs for generated-only editor tests.

## Failure handling

- A missing or mismatched pinned executable, decoder DLL, editor dependency,
  GUI automation capability, timeout, or unsupported editor build makes Task
  2 explicitly blocked; it does not fall back silently to direct
  serialization.
- A package that opens but changes a source pixel, loses mask sharing, changes
  order, or omits a companion file fails the round-trip test.
- If automation cannot reliably create a project after the controlled spike,
  a new design decision is required before attempting a standalone writer.

## Acceptance evidence

- The integration test proves reopened source pixels equal inputs and exactly
  one custom comparison bitmap remains shared by the first two references.
- The original editor opens the saved project, accepts a fresh save, and emits
  a runtime export.
- The recorded manifest names all observed companion files and their hashes;
  the generated golden package is reopenable on the same pinned build.
