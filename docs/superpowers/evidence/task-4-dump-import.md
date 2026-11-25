# Task 4 dump import evidence

## Qualified local input

`C:\DMD Colorization\DMD Mask Optimizer V4\twst_405.txt` was streamed by the
strict `timestamped-text-v1` reader. Its SHA-256 is
`f711aec5d42fdc423ca02bfd2c8f05c158afaee27a97acdbf59d532b81095b11` and its
size is 60,285,082 bytes.

The run read 14,443 complete records, each with 4,096 row-major native shade
bytes. The observed shade set is `{0, 1, 2, 3}`. The first tick is
`0x00088b41`; the last is `0x00227c3f`. There are 4,142 repeated pixel payload
occurrences, all retained as distinct occurrence records. The file contains one
monotonic timestamp session; the final occurrence has no next duration and is
marked `final-unknown`.

Each record requires an eight-hex-digit `0x` timestamp header, exactly 32 rows
of 128 ASCII shade symbols, and an empty line delimiter. The parser accepts LF
and CRLF records and records header byte offset, exclusive end offset, and
one-based header line. It rejects partial EOF, rows with an incorrect length,
invalid/native non-ASCII shade symbols, overflow/malformed timestamps, missing
delimiters, and an empty file with a typed `DumpParseError`.

## Timing scope

No selected producer source or local producer documentation in this workspace
establishes the tick unit or reset/wrap encoding. The profile therefore retains
`tick_unit: null` and `discontinuity_policy: split-unknown`. Equal ticks keep a
zero observed duration; any decreasing tick ends the prior occurrence with
`discontinuity` and starts a new session. Timed replay is outside this task
until producer evidence can support a unit and discontinuity policy.

## Reproduction

From the repository root:

```powershell
$taskDeps = Join-Path $PWD 'artifacts\task3-test-deps'
$env:PYTHONPATH = "$taskDeps;$PWD\src;$PWD"
$env:DMD_TWISTER_DUMP = 'C:\DMD Colorization\DMD Mask Optimizer V4\twst_405.txt'
& 'C:\DMD Colorization\DMD Mask Optimizer V4\.venv\Scripts\python.exe' -m pytest tests\unit\test_text_dump.py tests\local\test_twister_dump.py tests\integration\test_profile.py -q -p no:cacheprovider --basetemp=artifacts\task4-focused
```

The final qualification result was `138 passed, 17 skipped in 40.90s`. The local test
uses streaming iteration and retains only digests for repeat counting; it does
not accumulate the 59 MB pixel corpus in memory.
