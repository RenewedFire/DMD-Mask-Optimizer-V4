# Task 1 Local Runtime Baseline

## Intent

Complete Task 1's compatibility profile using the active, user-provided
runtime in `C:\vPinball\VisualPinball\VPinMAME`. This lets the project make
reproducible claims about the binaries it actually tests without claiming that
they were byte-compared to an unavailable upstream archive.

## Goals

- Pin the active `VPinMAME64.dll`, `Bass64.dll`, and `serum64.dll` by path,
  SHA-256, architecture, and file version.
- Retain the existing Twister ROM/dump identity checks.
- Make native locking pass only for that declared local baseline.
- Record the unavailable upstream-archive hash as a provenance limitation,
  rather than treating it as a binary-integrity failure.

## Non-goals

- Do not claim byte identity with the GitHub release archive.
- Do not claim Serum 2.5.2 matching parity with ColorizingDMD until a separate
  runtime parity test exists.
- Do not alter or replace any files under `C:\vPinball`.

## Approaches

1. Keep an upstream-archive requirement. This is strongest for release
   provenance, but cannot complete while the archive bytes are unavailable.
2. Pin the active local runtime with an explicit provenance limitation. This
   gives an exact, testable development baseline while keeping the limitation
   visible. **Chosen by the user.**

## Design

The profile records the active VPinMAME folder as a local baseline and marks
the archive hash unavailable. `lock_profile.py` verifies the three declared
binaries and dependencies by SHA-256, PE architecture, and file version. It
allows a local baseline without an archive hash only when its explicit
provenance state says `local-installation`; any other missing archive hash
remains invalid. Tests cover acceptance of the local baseline and rejection of
an empty/incorrect local provenance declaration.
