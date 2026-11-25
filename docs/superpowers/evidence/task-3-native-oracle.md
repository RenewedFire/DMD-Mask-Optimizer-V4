# Task 3 native replay evidence

**The original three-reference export fails recognition with the pinned Serum 2.1.0 DLL.** Task 3 native certification remains open. The oracle verifies the archive and checks the decoder layout before launch. Passing diagnostic runs use separately identified synthetic files.

## Editor and decoder layout

The committed `twst_405.cRZ` at `1e65ed6` has SHA-256 `06c2c489aae7d55fec68e1648b88192c842d3ac30bd114201487c48d49df5271`. The pinned DLL has SHA-256 `da71fa73e838ab3e257a2a73c8f74d88a3336615930761fa494a251822e0c2d5` and returns version `2.1.0`.

The editor writes a four-byte `is256x64` after the two-byte background count. Its hashes start at byte 106. The decoder reads the first hash at 102, interprets bytes 114 through 116 as shape modes 101, 66 and 125, and reads 245 as the first mask slot in a one-mask file. A direct isolated probe of the original export returned a valid load handle. Colorizing the first reference produced a native read fault in one run and no reported match in another. A successful load alone does not qualify this export. [Pinned editor serializer](https://github.com/SerumColor/ColorizingDMD/blob/37216912eecfb0cebf1e8c2e816d350d33f5e62d/ColorizingDMD.cpp) and [decoder array reader and Identify_Frame](https://github.com/SerumColor/ColorizingDMD/blob/37216912eecfb0cebf1e8c2e816d350d33f5e62d/serum-decode.cpp).

For the diagnostic control, the test removes bytes 102 through 105 from a copy of the unpacked synthetic fixture and repacks one member with a fixed ZIP timestamp. The resulting archive SHA-256 is `50af8c7e115cd74744c030f2be4f0e1d0b9ca5d6d8efda6b295ac2a4c4bbf73c`. This change was tested only on this generated file. The production replay API always stages the exact export from the caller's manifest. The incompatible original fails preflight.

## Native observations on the diagnostic control

The worker loads one verified DLL, requests both resolutions as the editor does, and records the 128 by 32 RGB565 plane. Observer mode also reads the public tester `frameID`. A separate production-mode process omits that read. Both modes produced identical result words, flags, triggers, rotation timers, widths, and hashes of emitted 32p frames across all five traces. The seed pictures supply distinct visible output. Rendered RGB565 SHA-256 prefixes for A, B and C were `2dba690b2eff`, `157827e58c2c`, and `23303d1ff92d`. [Public tester ABI](https://github.com/SerumColor/ColorizingDMD/blob/37216912eecfb0cebf1e8c2e816d350d33f5e62d/serum.h).

| Input / state | Native observation |
| --- | --- |
| A, A with pixel 4 changed, A with visible pixel 7 changed | A, A, unknown |
| B followed by identical B | Both calls emit B with its tester ordinal |
| Exact C, repeat C, C with one shade changed, exact C again | C emits once, the repeat and final C retain C, and the shade change is unknown |
| Reset, all-zero input, C, advance 1 ms | Unknown, newly emitted C, rotation call returns zero |
| Both masked refs given an all-one bitmap and hash zero | Zero input, C and B all select the first reference A |
| Add a masked A versus exact C ambiguity, order C/A/B | C, B, C, reset, C select C, B, A, C |
| Same ambiguity, order A/C/B | The same inputs select A, B, A, A |

The normal comparator traverses row-major bytes and hashes native values 0 through 3 with reflected CRC-32. Nonzero mask bytes omit positions entirely. A and B compare 4095 bytes with CRCs `b52ee996` and `de0c37ff`. C compares 4096 with CRC `f57d4265`. An all-hidden mask hashes the empty sequence to zero. Beginning at the previous winner, the matcher tests the whole current mask and comparison-mode group in cyclic reference order before changing groups. The C/A/B experiment exercises a group that wraps past ordinal zero. Reset creates a new process and restores ordinal-zero search.

The DLL reports `ffffffff` for both an unmasked repeat and an unknown. For an unchanged normal unmasked CRC the adapter labels the retained ID `unchanged-crc`. Newly emitted IDs are labeled `frameID`. Both cases retain the actual native result and no emitted pixel hash when the renderer receives no update.

Flipping the low bit at offsets 0, 6, 9, 10, 16, 20, 21, 22, 24, 25, 27, 28, 30, 31 and 32 in C gives unequal compared bytes, the same `f57d4265` CRC, and a native C match from reset. The altered frame's SHA-256 is `ab0c59bb8d03dd76c70c7b356e29bdf3e8bd740180c664bde8d1e1230cab6b23`. Changing only A's ignored byte instead gives identical compared bytes.

## Reproduction

From an x64 MSVC developer shell, compile the worker into the repository artifacts directory. Set `DMD_EDITOR_DECODER_PATH` to the source-tree DLL from the profile. The default worker location is shown below. `DMD_SERUM_WORKER` can select a different built worker.

```powershell
New-Item -ItemType Directory -Force artifacts/oracle | Out-Null
cl /nologo /std:c++17 /EHsc /O2 /Foartifacts/oracle/serum_worker.obj native/serum_worker.cpp /link /out:artifacts/oracle/serum_worker.exe
python -m pytest -q tests/integration/test_oracle.py -p no:cacheprovider --basetemp=artifacts/oracle/pytest
```

The first test run reported the missing oracle module. The final focused run exercised all nine cases, including malformed packets, input validation, shutdown, and a timed-out child alongside a healthy worker. Logs, worker build command, binary, export and source fingerprints, input hashes and event-by-event comparison results are in `artifacts/oracle-qualification`. The tests verify real elapsed-time waits with native rotation calls on these static frames. Animated scene timing and end-to-end playback of an original editor export remain unqualified.
