from __future__ import annotations


def test_diagnostic_verification_accounts_for_mapped_and_omitted_occurrences():
    from dmd_optimizer.export.compile import CompiledSelection
    from dmd_optimizer.verify.exported import verify_export

    selection = CompiledSelection(
        "revision", "pool", "families", "solution", (),
        (("capture", 0, "frame-a", "family-a", "mapped"), ("capture", 1, "frame-b", None, "omitted")),
        (("frame-b", "editor capacity"),),
    )
    record = verify_export(selection)

    assert record.input_occurrences == 2
    assert record.mapped_occurrences == 1
    assert record.omitted_occurrences == 1
    assert record.wrong_family_matches == 0
    assert not record.native_verified


def test_diagnostic_verification_rejects_unexplained_occurrence():
    from dmd_optimizer.export.compile import CompiledSelection
    from dmd_optimizer.verify.exported import ExportVerificationError, verify_export

    selection = CompiledSelection("r", "p", "f", "s", (), (("capture", 0, "frame", None, "unknown"),), ())
    try:
        verify_export(selection)
    except ExportVerificationError as error:
        assert "unexplained" in str(error)
    else:
        raise AssertionError("unexplained occurrences must reject diagnostic publication")
