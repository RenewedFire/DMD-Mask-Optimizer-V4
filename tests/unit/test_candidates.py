import pytest

from dmd_optimizer.families.model import Family


def _family(domain, ignore=(), compare=(0, 1, 2, 3)):
    return Family("family", "established-finite", "c", "l", "a", "ref", ("ref",), tuple(domain), tuple(ignore), tuple(compare), (), None)


def test_candidate_requires_variability_mask_and_rejects_negative():
    from dmd_optimizer.masks import Rejection, check_candidate
    family = _family((b"\x00\x00\x00\x00", b"\x01\x00\x00\x00"), (0,), (1, 2, 3))
    valid = check_candidate(family, family.domain_pixels[0], b"\x01\x00\x00\x00", (b"\x00\x00\x00\x01",), width=2, height=2, native_shades=4)
    assert not isinstance(valid, Rejection)
    assert check_candidate(family, family.domain_pixels[0], None, (), width=2, height=2, native_shades=4).reason == "positive-variability"
    assert check_candidate(family, family.domain_pixels[0], b"\x01\x01\x00\x00", (), width=2, height=2, native_shades=4).reason == "must-compare-violation"


def test_candidate_rejects_same_compared_bytes_for_negative():
    from dmd_optimizer.masks import Rejection, check_candidate
    family = _family((b"\x00\x00\x00\x00",), (0,), (1, 2, 3))
    result = check_candidate(family, b"\x00\x00\x00\x00", b"\x01\x00\x00\x00", (b"\x03\x00\x00\x00",), width=2, height=2, native_shades=4)
    assert isinstance(result, Rejection) and result.reason == "equal-compared-bytes"


def test_generate_reports_option_and_unrepresentable_family():
    from types import SimpleNamespace
    from dmd_optimizer.families.model import FamilySet
    from dmd_optimizer.masks import generate
    good = _family((b"\x01\x00\x00\x00",), (), (0, 1, 2, 3))
    bad = Family("bad", "observed-only", "c", "l", "a", "bad", ("bad",), (b"\x00\x00\x00\x00",), (), (0, 1, 2, 3), (), None)
    families = FamilySet(1, "finite-families-v1", "r", "p", (good, bad), (), (), "f")
    pool = generate(families, SimpleNamespace(digest="r"), SimpleNamespace(width=2, height=2, native_shades=4, profile_sha256="p"), project=None)
    assert {option.family_id for option in pool.options} == {"bad", "family"}
    assert pool.families_without_options == ()


def test_generate_offers_deduplicated_required_mask_unions_to_each_family():
    from types import SimpleNamespace
    from dmd_optimizer.families.model import FamilySet
    from dmd_optimizer.masks import generate

    left = _family((b"\x00\x00\x00\x00", b"\x01\x00\x00\x00"), (0,), (2, 3))
    right = Family("right", "established-finite", "c", "l", "a", "right", ("right",),
                   (b"\x00\x00\x01\x00", b"\x00\x01\x01\x00"), (1,), (2, 3), (), None)
    families = FamilySet(1, "finite-families-v1", "r", "p", (left, right), (), (), "f")

    pool = generate(families, SimpleNamespace(digest="r"),
                    SimpleNamespace(width=2, height=2, native_shades=4, profile_sha256="p"), project=None)

    shared = [item for item in pool.options if item.ignore == b"\x01\x01\x00\x00"]
    assert {item.family_id for item in shared} == {"family", "right"}
    assert len({item.mask_id for item in shared}) == 1


def test_custom_mask_identity_includes_geometry_and_rejection_keeps_mask_id():
    from dmd_optimizer.masks import Rejection, check_candidate

    family = _family((b"\x00\x00\x00\x00",), (), (1, 2, 3))
    first = check_candidate(family, b"\x00\x00\x00\x00", b"\x01\x00\x00\x00", (b"\x00\x00\x00\x00",), width=2, height=2, native_shades=4)
    second = check_candidate(family, b"\x00\x00\x00\x00", b"\x01\x00\x00\x00", (), width=1, height=4, native_shades=4)

    assert isinstance(first, Rejection) and first.mask_id is not None
    assert not isinstance(second, Rejection)
    assert first.mask_id != second.mask_id


def test_generate_is_stable_when_equivalent_families_are_reordered():
    from types import SimpleNamespace
    from dmd_optimizer.families.model import FamilySet
    from dmd_optimizer.masks import generate

    alpha = _family((b"\x00\x00\x00\x00",), (), (0, 1, 2, 3))
    beta = Family("beta", "observed-only", "c", "l", "a", "beta", ("beta",), (b"\x01\x00\x00\x00",), (), (0, 1, 2, 3), (), None)
    profile = SimpleNamespace(width=2, height=2, native_shades=4, profile_sha256="p")
    left = generate(FamilySet(1, "finite-families-v1", "r", "p", (alpha, beta), (), (), "f"), SimpleNamespace(digest="r"), profile, project=None)
    right = generate(FamilySet(1, "finite-families-v1", "r", "p", (beta, alpha), (), (), "f"), SimpleNamespace(digest="r"), profile, project=None)

    assert left == right


def test_generate_rejects_a_family_domain_that_cannot_match_the_profile():
    from types import SimpleNamespace
    from dmd_optimizer.families.model import FamilySet
    from dmd_optimizer.masks import generate

    broken = _family((b"\x00\x00\x00",), (), (0, 1, 2))
    families = FamilySet(1, "finite-families-v1", "r", "p", (broken,), (), (), "f")
    with pytest.raises(ValueError, match="family domain"):
        generate(families, SimpleNamespace(digest="r"), SimpleNamespace(width=2, height=2, native_shades=4, profile_sha256="p"), project=None)


def test_checker_rejects_a_real_crc32_collision_from_the_task3_fixture():
    from pathlib import Path
    from dmd_optimizer.masks import Rejection, check_candidate

    payload = (Path(__file__).parents[1] / "fixtures" / "editor_roundtrip" / "golden" / "twst_405.cRP").read_bytes()
    reference = payload[64 + 2 * 4096:64 + 3 * 4096]
    collision = bytearray(reference)
    for index in (0, 6, 9, 10, 16, 20, 21, 22, 24, 25, 27, 28, 30, 31, 32):
        collision[index] ^= 1
    family = Family("collision", "observed-only", "c", "l", "a", "ref", ("ref",), (reference,), (), tuple(range(4096)), (), None)

    result = check_candidate(family, reference, None, (bytes(collision),), width=128, height=32, native_shades=4)

    assert isinstance(result, Rejection)
    assert result.reason == "crc-collision"
    assert result.witness_pixels == bytes(collision)


def test_identical_contextual_inputs_have_no_discriminating_option():
    from types import SimpleNamespace
    from dmd_optimizer.families.model import FamilySet
    from dmd_optimizer.masks import generate

    left = _family((b"\x00\x00\x00\x00",), (), (0, 1, 2, 3))
    right = Family("right", "observed-only", "c", "l", "a", "right", ("right",), (b"\x00\x00\x00\x00",), (), (0, 1, 2, 3), (), None)
    pool = generate(FamilySet(1, "finite-families-v1", "r", "p", (left, right), (), (), "f"), SimpleNamespace(digest="r"), SimpleNamespace(width=2, height=2, native_shades=4, profile_sha256="p"), project=None)

    assert pool.options == ()
    assert pool.families_without_options == ("family", "right")
    assert {item.reason for item in pool.rejections} == {"equal-compared-bytes"}


def test_pairwise_sharing_does_not_validate_three_way_union():
    from dmd_optimizer.masks import Rejection, check_candidate

    left = _family((b"\x00\x00\x00\x00", b"\x01\x00\x00\x00"), (0,), (3,))
    right = Family("right", "established-finite", "c", "l", "a", "right", ("right",), (b"\x00\x00\x01\x00", b"\x00\x01\x01\x00"), (1,), (3,), (), None)
    third = Family("third", "established-finite", "c", "l", "a", "third", ("third",), (b"\x00\x00\x00\x00", b"\x00\x00\x01\x00"), (2,), (3,), (), None)

    pair = check_candidate(left, left.domain_pixels[0], b"\x01\x01\x00\x00", right.domain_pixels, width=2, height=2, native_shades=4)
    triple = check_candidate(left, left.domain_pixels[0], b"\x01\x01\x01\x00", right.domain_pixels + third.domain_pixels, width=2, height=2, native_shades=4)

    assert not isinstance(pair, Rejection)
    assert isinstance(triple, Rejection)
    assert triple.reason == "equal-compared-bytes"
