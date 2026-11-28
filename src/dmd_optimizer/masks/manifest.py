"""Canonical, validated option-pool publication for Task 10."""

from __future__ import annotations

import json
import os
from dataclasses import asdict
from pathlib import Path

from .model import MaskOption, OptionPool, Rejection, option_pool_digest
from dmd_optimizer.families import read_family_set


class ManifestError(ValueError):
    pass


def _jsonable(value):
    if isinstance(value, bytes):
        return {"bytes": value.hex()}
    if isinstance(value, tuple):
        return [_jsonable(item) for item in value]
    if isinstance(value, dict):
        return {key: _jsonable(item) for key, item in value.items()}
    return value


def _bytes(value) -> bytes:
    if not isinstance(value, dict) or set(value) != {"bytes"} or not isinstance(value["bytes"], str):
        raise ManifestError("invalid byte payload")
    try:
        return bytes.fromhex(value["bytes"])
    except ValueError as error:
        raise ManifestError("invalid byte payload") from error


def _option(raw: dict) -> MaskOption:
    ignore = raw["ignore"]
    return MaskOption(raw["option_id"], raw["family_id"], raw["reference_frame_id"], raw["mask_id"],
                      None if ignore is None else _bytes(ignore), raw["crc32"], raw["shape"],
                      raw["positive_count"], raw["negative_count"], raw["domain_digest"])


def _rejection(raw: dict) -> Rejection:
    witness = raw["witness_pixels"]
    return Rejection(raw["family_id"], raw["mask_id"], raw["reason"], raw["input_digest"],
                     raw["expected_crc"], raw["actual_crc"], None if witness is None else _bytes(witness))


def _validate(pool: OptionPool, allowed_family_ids: set[str] | None = None) -> OptionPool:
    if pool.schema_version != 1 or pool.algorithm_version != "mask-candidates-v1":
        raise ManifestError("unsupported option pool schema or algorithm")
    if pool.generation_limits != (256, 64) or not isinstance(pool.search_complete, bool):
        raise ManifestError("invalid generation metadata")
    referenced_family_ids = {option.family_id for option in pool.options} | {item.family_id for item in pool.rejections} | set(pool.families_without_options)
    if not referenced_family_ids or len({option.option_id for option in pool.options}) != len(pool.options):
        raise ManifestError("invalid option identities")
    if allowed_family_ids is not None and referenced_family_ids - allowed_family_ids:
        raise ManifestError("unknown family target")
    for option in pool.options:
        if option.shape or option.positive_count < 1 or option.negative_count < 0:
            raise ManifestError("invalid option")
        if option.ignore is None and option.mask_id is not None:
            raise ManifestError("inconsistent unmasked option")
        if option.ignore is not None and (not any(option.ignore) or option.mask_id is None or any(value not in (0, 1) for value in option.ignore)):
            raise ManifestError("invalid option bitmap")
    if option_pool_digest(pool) != pool.digest:
        raise ManifestError("option pool digest mismatch")
    return pool


def write_option_pool(pool: OptionPool, path: Path) -> None:
    path = Path(path)
    families = read_family_set(path.with_name("families.json"))
    if families.digest != pool.family_digest or families.revision_digest != pool.revision_digest or families.profile_sha256 != pool.profile_sha256:
        raise ManifestError("family handoff identity mismatch")
    _validate(pool, {item.family_id for item in families.families})
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(_jsonable(asdict(pool)), sort_keys=True, separators=(",", ":"), ensure_ascii=False), encoding="utf-8")
    os.replace(temporary, path)


def read_option_pool(path: Path) -> OptionPool:
    try:
        raw = json.loads(Path(path).read_text(encoding="utf-8"))
        pool = OptionPool(raw["schema_version"], raw["algorithm_version"], raw["revision_digest"], raw["family_digest"],
                          raw["profile_sha256"], raw["scope_digest"], tuple(raw["generation_limits"]),
                          tuple(_option(item) for item in raw["options"]), tuple(_rejection(item) for item in raw["rejections"]),
                          tuple(raw["families_without_options"]), raw["search_complete"], raw["digest"])
        families = read_family_set(Path(path).with_name("families.json"))
        if families.digest != pool.family_digest or families.revision_digest != pool.revision_digest or families.profile_sha256 != pool.profile_sha256:
            raise ManifestError("family handoff identity mismatch")
        return _validate(pool, {item.family_id for item in families.families})
    except (OSError, KeyError, TypeError, json.JSONDecodeError, ManifestError) as error:
        if isinstance(error, ManifestError):
            raise
        raise ManifestError(f"invalid option pool manifest: {path}") from error
