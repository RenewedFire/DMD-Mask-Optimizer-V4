# Task 6 VPinMAME Dump Import Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans for inline execution. Preserve existing uncommitted work and leave all changes uncommitted for the user.

**Goal:** Treat VPinMAME's built-in per-ROM DMD text dumps as the supported acquisition format and import explicitly selected dump files into the optimizer corpus.

**Architecture:** VPinMAME records frames during normal play or attract mode into its `dmddump` directory. The optimizer runs later, reads explicitly selected `.txt` files through the existing strict `timestamped-text-v1` parser, and appends each file as its own immutable corpus capture. It does not launch PinMAME, watch `dmddump`, alter VPinMAME configuration, or maintain a second live recorder.

**Tech Stack:** Existing Python dump parser and corpus store; VPinMAME's installed dump feature.

**Spec:** `DMD_Mask_Optimizer_Design_and_Implementation_Plan.md`, sections 6 and 22; replaces the superseded live-capture interpretation of Task 6.

## Global Constraints

- VPinMAME remains the sole producer. The optimizer must not start, configure, or interfere with it.
- Users explicitly select one or more completed dump files; folder watching and automatic import are out of scope.
- Each source file remains a separate corpus capture with its own SHA-256, path, producer configuration, occurrence order, repeats, ticks, and source positions.
- Accept only the proven `timestamped-text-v1` grammar: 128x32 native values `0`--`3`, a hexadecimal tick header, and a blank delimiter.
- A malformed or incomplete dump fails without creating a corpus revision. Unknown tick units remain unknown.

## Completed foundation

- Task 4's `read_dump(path, profile)` is a streaming, strict reader that preserves every occurrence including repeated frames and raw ticks.
- Task 5's `append_capture(project, source, occurrences)` writes each input as an immutable capture and can append additional captures to the same Twister corpus.
- Local installation evidence confirms VPinMAME's `dmddump` directory, F6 text dumping, and raw-output configuration option. No configuration was changed.

## Completion Gate

Task 6 is complete when a user-selected VPinMAME `twst_405` dump has passed the strict reader and corpus round trip, with its own provenance, and when the documented workflow explains how additional completed dump files are added as separate captures. It does not certify complete gameplay coverage; that remains Task 7.

## Execution result — 2026-11-25

Completed. `C:\\vPinball\\VisualPinball\\VPinMAME\\dmddump\\twst_405.txt`
streamed successfully as 15,291 occurrences and was stored as one complete
worktree-only corpus capture. Reopening the resulting revision returned all
15,291 occurrences and verified the first stored native frame against the
source dump byte-for-byte. Revision:
`adef8406a191f4c6814572b991229ab5b89224f0d70cc04d74fbe3ead115c589`.
