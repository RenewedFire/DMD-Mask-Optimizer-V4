# Three-reference editor round trip

The generated project is in `artifacts/roundtrip-1271826243d7/project`. The compact golden copy and reference-ID mapping are in `tests/fixtures/editor_roundtrip/golden`. All three references came from the synthetic test fixture.

The staged editor imported the TXT, applied comparison slot 0 to frames A and B, and saved the project. Frame C retained sentinel 255. The first process, PID 17780, exited with zero active job members. The first implementation tried to reuse that transaction for its next job. Windows denied publication of the second job marker before another editor launched. The bridge restored and verified the settings. Its original diagnostic is in `project-editor-config/bridge.stdout` under the run directory.

The corrected bridge uses one journaled transaction per editor process while keeping exclusive ownership across a normal round trip. For this run, the continuation checked the first-session diagnostic and the hashes of all three generated files before calling the production reopen operation on the same directory. PID 8892 opened the .cROM and its companion .cRP through the editor's Open button. Its title reported three frames. Save updated the write times of all three output files and the pinned Serum DLL accepted a byte-identical copy of the resulting .cRZ. The second job also reached zero active processes, settings restoration verified, and the incomplete marker was absent. The response is in `reopen.stdout`. The first editor session was run once.

| Freshly saved file | Bytes | SHA-256 |
| --- | ---: | --- |
| twst_405.cROM | 256052 | `d020f1e55a9b1d356c039b8035d42456eaf22c3cfcb576849cf8a864f38e996a` |
| twst_405.cRP | 135003 | `55fc06c36a869c4b18472db3336fc5b681e5074c33b5d23a7d2ae801b8a3ea7e` |
| twst_405.cRZ | 565 | `06c2c489aae7d55fec68e1648b88192c842d3ac30bd114201487c48d49df5271` |

The pinned .cROM starts with a 64-byte ROM name. Byte 64 begins nine little-endian uint32 fields, a uint16 background count, and a four-byte Windows BOOL. Their observed values are `80, 128, 32, 256, 64, 3, 4, 1, 0, 0, 0`. Three four-byte frame hashes follow at byte 106. Bytes 118–120 are zero, confirming normal comparison. Bytes 121–123 contain the three slot IDs `0, 0, 255`. Bytes 124–4219 contain the shared bitmap, with only pixel (4,0) set.

In the .cRP, three consecutive 4096-byte source frames start at byte 64. Their pixels match A, B, and C in order, including the ignored position where A and B differ. The .cRZ contains one member named `twst_405.cRom` whose extracted bytes equal the saved .cROM. The full manifest passed the bridge v1 JSON Schema and the Python adapter's file, reference and runtime-package checks.

To run the full workflow on a new fixture, set the usual locked staging inputs, set `DMD_EDITOR_ROUNDTRIP=1`, and run `tests/integration/test_editor_roundtrip.py::test_original_editor_roundtrip`. The non-GUI golden test checks the committed package independently. The separate 64/65 mask-boundary experiment remains untested.
