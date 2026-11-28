from __future__ import annotations


def test_publish_diagnostic_bundle_uses_fresh_atomic_directory(tmp_path):
    from dmd_optimizer.export.compile import CompiledSelection
    from dmd_optimizer.export.publish import publish_diagnostic

    selection = CompiledSelection("r", "p", "f", "s", (), (("cap", 0, "frame", "family", "mapped"),), ())
    record = publish_diagnostic(selection, tmp_path / "runs", reasons=("bridge request limit exceeded",))

    assert record.status == "diagnostic-only"
    assert record.folder.is_dir()
    assert (record.folder / "diagnostic.json").is_file()
    assert (record.folder / "inventory.json").is_file()
    assert not list((tmp_path / "runs").glob("*.staging"))


def test_publish_diagnostic_bundle_does_not_overwrite_existing_run(tmp_path):
    from dmd_optimizer.export.compile import CompiledSelection
    from dmd_optimizer.export.publish import ExportPublishError, publish_diagnostic

    selection = CompiledSelection("r", "p", "f", "s", (), (), ())
    root = tmp_path / "runs"
    first = publish_diagnostic(selection, root, reasons=("capacity",), run_id="fixed")
    assert first.folder.name == "fixed"
    try:
        publish_diagnostic(selection, root, reasons=("capacity",), run_id="fixed")
    except ExportPublishError as error:
        assert "already exists" in str(error)
    else:
        raise AssertionError("existing output must not be overwritten")
