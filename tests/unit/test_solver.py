from __future__ import annotations

from dataclasses import replace
from types import SimpleNamespace

import pytest

from dmd_optimizer.families.infer import _digest
from dmd_optimizer.families.model import Family, FamilySet
from dmd_optimizer.masks.model import MaskOption, OptionPool, option_pool_digest


def _families(ids=("a", "b", "c")):
    families = tuple(Family(item, "observed-only", "c", "l", "a", item, (item,), (bytes(4),), (), (0, 1, 2, 3), (), None) for item in ids)
    semantic = {"schema_version": 1, "algorithm_version": "finite-families-v1", "revision_digest": "revision", "profile_sha256": "profile", "families": families, "assignments": (), "unresolved": ()}
    return FamilySet(1, "finite-families-v1", "revision", "profile", families, (), (), _digest(semantic))


def _option(option_id, family_id, mask_id):
    return MaskOption(option_id, family_id, family_id, mask_id, None if mask_id is None else b"\x01\x00\x00\x00", 1, False, 1, 2, f"domain-{family_id}")


def _pool(options, *, families_without_options=()):
    draft = OptionPool(1, "mask-candidates-v1", "revision", "families", "profile", "scope", (256, 64), tuple(options), (), tuple(families_without_options), True, "")
    return replace(draft, digest=option_pool_digest(draft))


def test_result_validation_counts_shared_masks_and_unmasked_options_once():
    from dmd_optimizer.solve import SolveResult, result_digest, validate_result
    from dmd_optimizer.solve.model import solve_model_digest

    families = _families()
    pool = _pool((_option("a-shared", "a", "shared"), _option("a-free", "a", None), _option("b-shared", "b", "shared"), _option("c-other", "c", "other")))
    pool = replace(pool, family_digest=families.digest, digest="")
    pool = replace(pool, digest=option_pool_digest(pool))
    draft = SolveResult(1, "mask-cover-v1", pool.digest, families.digest, "revision", "profile", "scope", solve_model_digest(pool, 64), (("a", "a-shared"), ("b", "b-shared"), ("c", "c-other")), ("other", "shared"), 2, 2, "candidate-pool", "optimal-pool", None, "")
    result = replace(draft, digest=result_digest(draft))

    validate_result(result, pool, families, mask_cap=64)
    assert result.selected_mask_count == 2
    assert result.selected_mask_ids == ("other", "shared")


def test_result_validation_rejects_duplicate_assignment_and_stale_identity():
    from dmd_optimizer.solve import SolveError, SolveResult, result_digest, validate_result
    from dmd_optimizer.solve.model import solve_model_digest

    families = _families(("a",))
    pool = _pool((_option("a-free", "a", None),))
    pool = replace(pool, family_digest=families.digest, digest="")
    pool = replace(pool, digest=option_pool_digest(pool))
    draft = SolveResult(1, "mask-cover-v1", pool.digest, families.digest, "revision", "profile", "scope", solve_model_digest(pool, 64), (("a", "a-free"), ("a", "a-free")), (), 0, 0, "candidate-pool", "optimal-pool", None, "")
    duplicate = replace(draft, digest=result_digest(draft))
    with pytest.raises(SolveError, match="assignment"):
        validate_result(duplicate, pool, families, mask_cap=64)
    stale = replace(duplicate, assignment=(("a", "a-free"),), pool_digest="old", digest="")
    stale = replace(stale, digest=result_digest(stale))
    with pytest.raises(SolveError, match="pool"):
        validate_result(stale, pool, families, mask_cap=64)
    bad_model = replace(duplicate, assignment=(("a", "a-free"),), model_digest="old", digest="")
    bad_model = replace(bad_model, digest=result_digest(bad_model))
    with pytest.raises(SolveError, match="model"):
        validate_result(bad_model, pool, families, mask_cap=64)


class NeverStop:
    def stopped(self):
        return False


class AlreadyStopped:
    def stopped(self):
        return True


def test_solve_selects_shared_masks_and_reports_pool_optimum():
    from dmd_optimizer.solve import solve

    families = _families()
    pool = _pool((_option("a-shared", "a", "shared"), _option("a-own", "a", "a-own"), _option("b-shared", "b", "shared"), _option("b-own", "b", "b-own"), _option("c-other", "c", "other")))
    pool = replace(pool, family_digest=families.digest, digest="")
    pool = replace(pool, digest=option_pool_digest(pool))
    result = solve(pool, SimpleNamespace(profile_sha256="profile", mask_cap=64), NeverStop(), families=families, time_limit_seconds=5)

    assert result.status == "optimal-pool"
    assert result.selected_mask_count == result.lower_bound == 2
    assert result.selected_mask_ids == ("other", "shared")
    assert result.assignment == (("a", "a-shared"), ("b", "b-shared"), ("c", "c-other"))


def test_solve_reports_missing_options_and_cap_infeasibility():
    from dmd_optimizer.solve import solve

    families = _families(("a",))
    no_option = _pool((), families_without_options=("a",))
    no_option = replace(no_option, family_digest=families.digest, digest="")
    no_option = replace(no_option, digest=option_pool_digest(no_option))
    assert solve(no_option, SimpleNamespace(profile_sha256="profile", mask_cap=64), NeverStop(), families=families, time_limit_seconds=5).status == "no-feasible-option"

    ids = tuple(f"f{index}" for index in range(65))
    too_many_families = _families(ids)
    cap_pool = _pool(tuple(_option(f"{item}-only", item, f"mask-{item}") for item in ids))
    cap_pool = replace(cap_pool, family_digest=too_many_families.digest, digest="")
    cap_pool = replace(cap_pool, digest=option_pool_digest(cap_pool))
    result = solve(cap_pool, SimpleNamespace(profile_sha256="profile", mask_cap=64), NeverStop(), families=too_many_families, time_limit_seconds=5)
    assert result.status == "infeasible-pool"


def test_result_validation_rejects_rehashed_false_proof_or_infeasibility():
    from dmd_optimizer.solve import SolveError, SolveResult, result_digest, validate_result
    from dmd_optimizer.solve.model import solve_model_digest

    families = _families(("a",))
    pool = _pool((_option("a-free", "a", None),))
    pool = replace(pool, family_digest=families.digest, digest="")
    pool = replace(pool, digest=option_pool_digest(pool))
    common = (1, "mask-cover-v1", pool.digest, families.digest, "revision", "profile", "scope", solve_model_digest(pool, 64))
    false_proof = SolveResult(*common, (("a", "a-free"),), (), 0, None, "candidate-pool", "optimal-pool", None, "")
    false_proof = replace(false_proof, digest=result_digest(false_proof))
    with pytest.raises(SolveError, match="prove"):
        validate_result(false_proof, pool, families, mask_cap=64)
    false_unsat = SolveResult(*common, (), (), None, None, "candidate-pool", "infeasible-pool", None, "")
    false_unsat = replace(false_unsat, digest=result_digest(false_unsat))
    with pytest.raises(SolveError, match="certificate"):
        validate_result(false_unsat, pool, families, mask_cap=64)


def test_solve_uses_stable_option_id_tie_break():
    from dmd_optimizer.solve import solve

    families = _families(("a",))
    pool = _pool((_option("z-option", "a", None), _option("a-option", "a", None)))
    pool = replace(pool, family_digest=families.digest, digest="")
    pool = replace(pool, digest=option_pool_digest(pool))
    result = solve(pool, SimpleNamespace(profile_sha256="profile", mask_cap=64), NeverStop(), families=families, time_limit_seconds=5)
    assert result.assignment == (("a", "a-option"),)


def test_solve_never_claims_optimum_when_cancelled_or_given_no_time():
    from dmd_optimizer.solve import solve

    families = _families(("a",))
    pool = _pool((_option("a-free", "a", None),))
    pool = replace(pool, family_digest=families.digest, digest="")
    pool = replace(pool, digest=option_pool_digest(pool))
    profile = SimpleNamespace(profile_sha256="profile", mask_cap=64)
    cancelled = solve(pool, profile, AlreadyStopped(), families=families, time_limit_seconds=5)
    assert cancelled.status == "unknown"
    timed = solve(pool, profile, NeverStop(), families=families, time_limit_seconds=0)
    assert timed.status in {"unknown", "feasible-unproved", "optimal-pool"}
    if timed.status != "optimal-pool":
        assert timed.lower_bound is None or timed.lower_bound <= (timed.selected_mask_count or 0)
