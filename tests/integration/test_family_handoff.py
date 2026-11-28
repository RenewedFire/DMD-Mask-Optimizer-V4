from __future__ import annotations

from dmd_optimizer.capture.text_dump import OccurrenceInput
from dmd_optimizer.corpus import Capture, append_capture, iter_occurrences
from dmd_optimizer.explore.coverage import CoverageReport


def test_manifest_round_trip_is_stable_and_detects_tampering(tmp_path):
    from dmd_optimizer.families import infer
    from dmd_optimizer.families.manifest import ManifestError, read_family_set, write_family_set

    project = tmp_path / "corpus"
    source = Capture("a" * 64, "source", "test", None, {}, True, 2, 2, 4, "native-u8", "identity-v1", None, {}, "b" * 64, "c" * 64)
    rows = [OccurrenceInput(0, index, index, None, "final-unknown", index, index + 1, index + 1, pixels)
            for index, pixels in enumerate((b"\x00" * 4, b"\x01" * 4))]
    revision = append_capture(project, source, rows)
    first = next(iter(iter_occurrences(project, revision.digest)))
    coverage = CoverageReport(1, "dump-coverage-v1", revision.digest, "b" * 64, "c" * 64, 1, 2, 2, 0,
                              (), ((first.capture_id, 0),), (), None, "observed-only", (), "supplied-dumps")
    result = infer(revision, (), project=project, coverage=coverage)
    manifest = tmp_path / "families.json"
    write_family_set(result, manifest)

    assert read_family_set(manifest) == result
    content = manifest.read_text(encoding="utf-8")
    manifest.write_text(content.replace('"schema_version":1', '"schema_version":2'), encoding="utf-8")
    try:
        read_family_set(manifest)
    except ManifestError as error:
        assert "schema" in str(error)
    else:
        raise AssertionError("tampered manifest was accepted")
