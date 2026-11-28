from __future__ import annotations

from dataclasses import replace
from types import SimpleNamespace

import pytest

from dmd_optimizer.families.infer import _digest
from dmd_optimizer.families.manifest import write_family_set
from dmd_optimizer.families.model import Family, FamilySet
from dmd_optimizer.masks.manifest import write_option_pool
from dmd_optimizer.masks.model import MaskOption, OptionPool, option_pool_digest


def _handoff(tmp_path):
    family = Family("family", "observed-only", "c", "l", "a", "reference", ("reference",), (b"\x00\x00\x00\x00",), (), (0, 1, 2, 3), (), None)
    semantic = {"schema_version": 1, "algorithm_version": "finite-families-v1", "revision_digest": "revision", "profile_sha256": "profile", "families": (family,), "assignments": (), "unresolved": ()}
    families = FamilySet(1, "finite-families-v1", "revision", "profile", (family,), (), (), _digest(semantic))
    write_family_set(families, tmp_path / "families.json")
    option = MaskOption("option", "family", "reference", None, None, 1, False, 1, 0, "domain")
    pool = OptionPool(1, "mask-candidates-v1", "revision", families.digest, "profile", "scope", (256, 64), (option,), (), (), True, "")
    pool = replace(pool, digest=option_pool_digest(pool))
    pool_path = tmp_path / "options.json"
    write_option_pool(pool, pool_path)
    return families, pool, pool_path


class NeverStop:
    def stopped(self):
        return False


def test_solve_result_round_trip_revalidates_pool_and_profile(tmp_path):
    from dmd_optimizer.solve import read_solve_result, solve, write_solve_result

    families, pool, pool_path = _handoff(tmp_path)
    profile = SimpleNamespace(profile_sha256="profile", mask_cap=64)
    result = solve(pool, profile, NeverStop(), families=families, time_limit_seconds=5)
    path = tmp_path / "solution.json"
    write_solve_result(result, path, pool_path=pool_path, profile=profile)
    assert read_solve_result(path, pool_path=pool_path, profile=profile) == result
    with pytest.raises(ValueError, match="profile"):
        read_solve_result(path, pool_path=pool_path, profile=SimpleNamespace(profile_sha256="other", mask_cap=64))
