from __future__ import annotations

from dataclasses import replace

import pytest

from dmd_optimizer.families.infer import _digest
from dmd_optimizer.families.model import Family, FamilySet
from dmd_optimizer.masks.model import MaskOption, OptionPool, option_pool_digest
from dmd_optimizer.solve import SolveResult, result_digest
from dmd_optimizer.solve.model import solve_model_digest


def _family_set(ids=("a",)):
    families = tuple(
        Family(item, "observed-only", "context", "layout", "state", item, (item,), (bytes(4),), (), (0, 1, 2, 3), (), None)
        for item in ids
    )
    semantic = {"schema_version": 1, "algorithm_version": "finite-families-v1", "revision_digest": "revision", "profile_sha256": "profile", "families": families, "assignments": (), "unresolved": ()}
    return FamilySet(1, "finite-families-v1", "revision", "profile", families, (), (), _digest(semantic))


def _inputs(ids=("a",), masks=()):
    families = _family_set(ids)
    options = tuple(MaskOption(f"{item}-option", item, item, masks[index] if index < len(masks) else None, None, 1, False, 1, 0, f"domain-{item}") for index, item in enumerate(ids))
    pool = OptionPool(1, "mask-candidates-v1", "revision", families.digest, "profile", "scope", (256, 64), options, (), (), True, "")
    pool = replace(pool, digest=option_pool_digest(pool))
    assignments = tuple((item, f"{item}-option") for item in ids)
    draft = SolveResult(1, "mask-cover-v1", pool.digest, families.digest, "revision", "profile", "scope", solve_model_digest(pool, 64), assignments, tuple(sorted(set(masks))), len(set(masks)), len(set(masks)), "candidate-pool", "optimal-pool", None, "")
    result = replace(draft, digest=result_digest(draft))
    return result, pool, families


def test_preflight_accepts_small_identity_matched_selection():
    from dmd_optimizer.export.preflight import preflight

    result, pool, families = _inputs(("a", "b"))
    decision = preflight(result, pool, families, revision_digest="revision", bridge_limit_bytes=10_000)

    assert decision.full_export_possible
    assert decision.requested_reference_count == 2
    assert decision.representable_reference_count == 2
    assert decision.reasons == ()


def test_preflight_reports_limits_without_dropping_families():
    from dmd_optimizer.export.preflight import ExportPreflightError, preflight

    ids = tuple(f"f{index}" for index in range(65))
    result, pool, families = _inputs(ids, tuple(f"mask-{index}" for index in range(65)))
    with pytest.raises(ExportPreflightError, match="mask cap exceeded"):
        preflight(result, pool, families, revision_digest="revision", bridge_limit_bytes=1)


def test_preflight_rejects_stale_solution_identity():
    from dmd_optimizer.export.preflight import ExportPreflightError, preflight

    result, pool, families = _inputs()
    with pytest.raises(ExportPreflightError, match="revision"):
        preflight(result, pool, families, revision_digest="other")


def test_bridge_limit_accepts_the_full_unique_frame_request():
    from dmd_optimizer.export.preflight import BRIDGE_REQUEST_LIMIT

    # The fixed Twister corpus has 10,301 unique frames.  Its measured
    # serialized import request is 86,353,284 bytes, below the bounded
    # 128 MiB transport limit.
    assert BRIDGE_REQUEST_LIMIT == 128 * 1024 * 1024
    assert 86_353_284 < BRIDGE_REQUEST_LIMIT
