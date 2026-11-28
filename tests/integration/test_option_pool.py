from pathlib import Path

import pytest

from dataclasses import replace

from dmd_optimizer.families.infer import _digest
from dmd_optimizer.families.manifest import write_family_set
from dmd_optimizer.families.model import Family, FamilySet
from dmd_optimizer.masks.model import MaskOption, OptionPool, Rejection, option_pool_digest


def _pool() -> OptionPool:
    option = MaskOption(
        "option", "family", "reference", "mask", b"\x01\x00\x00\x00", 123,
        False, 1, 2, "domain",
    )
    rejection = Rejection("other", None, "equal-compared-bytes", "input", 123, 123, b"\x00\x00\x00\x00")
    return OptionPool(
        1, "mask-candidates-v1", "revision", "families", "profile", "scope", (256, 64),
        (option,), (rejection,), ("other",), True, "digest",
    )


def test_option_pool_round_trip_is_canonical_and_validated(tmp_path: Path):
    from dmd_optimizer.masks.manifest import ManifestError, read_option_pool, write_option_pool

    family = Family("family", "observed-only", "c", "l", "a", "reference", ("reference",), (b"\x00\x00\x00\x00",), (), (0, 1, 2, 3), (), None)
    other = Family("other", "observed-only", "c", "l", "a", "other-reference", ("other-reference",), (b"\x01\x00\x00\x00",), (), (0, 1, 2, 3), (), None)
    semantic = {"schema_version": 1, "algorithm_version": "finite-families-v1", "revision_digest": "revision", "profile_sha256": "profile", "families": (family, other), "assignments": (), "unresolved": ()}
    family_set = FamilySet(1, "finite-families-v1", "revision", "profile", (family, other), (), (), _digest(semantic))
    write_family_set(family_set, tmp_path / "families.json")
    path = tmp_path / "options.json"
    pool = _pool()
    pool = replace(pool, family_digest=family_set.digest)
    pool = replace(pool, digest=option_pool_digest(pool))
    write_option_pool(pool, path)
    first = path.read_bytes()
    write_option_pool(pool, path)
    assert path.read_bytes() == first
    assert read_option_pool(path) == pool

    forged = replace(pool, options=(replace(pool.options[0], family_id="unknown"),))
    forged = replace(forged, digest=option_pool_digest(forged))
    with pytest.raises(ManifestError, match="unknown family"):
        write_option_pool(forged, tmp_path / "forged.json")

    invalid_bitmap = replace(pool, options=(replace(pool.options[0], ignore=b"\x02\x00\x00\x00"),))
    invalid_bitmap = replace(invalid_bitmap, digest=option_pool_digest(invalid_bitmap))
    with pytest.raises(ManifestError, match="invalid option bitmap"):
        write_option_pool(invalid_bitmap, tmp_path / "invalid.json")

    duplicate = replace(pool, options=(pool.options[0], pool.options[0]))
    duplicate = replace(duplicate, digest=option_pool_digest(duplicate))
    with pytest.raises(ManifestError, match="invalid option identities"):
        write_option_pool(duplicate, tmp_path / "duplicate.json")
