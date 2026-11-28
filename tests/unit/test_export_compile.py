from __future__ import annotations

import csv
import hashlib


def test_write_separate_exports_preserves_stable_order_and_raw_pixels(tmp_path):
    from dmd_optimizer.export.compile import CompiledReference, CompiledSelection
    from dmd_optimizer.export.files import write_separate_exports

    selection = CompiledSelection(
        revision_digest="revision", pool_digest="pool", family_digest="families", solution_digest="solution",
        references=(
            CompiledReference("family-b", "option-b", "frame-b", bytes((1, 2, 3, 0)), None, 0),
            CompiledReference("family-a", "option-a", "frame-a", bytes((0, 3, 2, 1)), None, 1),
        ),
        occurrences=(("capture", 0, "frame-b", "family-b", "mapped"), ("capture", 1, "frame-a", "family-a", "mapped")),
        omissions=(),
    )
    inventory = write_separate_exports(selection, tmp_path / "bundle")

    assert inventory.file_count >= 6
    assert (tmp_path / "bundle" / "reference_frames" / "frame-b.bin").read_bytes() == bytes((1, 2, 3, 0))
    with (tmp_path / "bundle" / "frame_mapping.csv").open(newline="", encoding="utf-8") as stream:
        assert list(csv.DictReader(stream))[0]["family_id"] == "family-b"
    assert inventory.files["reference_frames/frame-a.bin"] == hashlib.sha256(bytes((0, 3, 2, 1))).hexdigest()


def test_write_separate_exports_rejects_duplicate_reference_ids(tmp_path):
    from dmd_optimizer.export.compile import CompiledReference, CompiledSelection
    from dmd_optimizer.export.files import ExportWriteError, write_separate_exports

    selection = CompiledSelection("r", "p", "f", "s", (
        CompiledReference("a", "one", "same", bytes(4), None, 0),
        CompiledReference("b", "two", "same", bytes(4), None, 1),
    ), (), ())
    try:
        write_separate_exports(selection, tmp_path / "bundle")
    except ExportWriteError as error:
        assert "duplicate" in str(error)
    else:
        raise AssertionError("duplicate reference IDs must be rejected")


def test_compile_records_maps_selected_family_and_marks_omission():
    from dmd_optimizer.export.compile import compile_records

    records = compile_records(
        {"frame-a": "family-a", "frame-b": "family-b"},
        {"family-a"},
        (("capture", 0, "frame-a"), ("capture", 1, "frame-b")),
    )

    assert records == (
        ("capture", 0, "frame-a", "family-a", "mapped"),
        ("capture", 1, "frame-b", "family-b", "omitted"),
    )
