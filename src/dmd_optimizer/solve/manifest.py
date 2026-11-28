"""Atomic Task 10 solve-result handoff for Task 11."""

from __future__ import annotations

import json
import os
from dataclasses import asdict
from pathlib import Path

from dmd_optimizer.families import read_family_set
from dmd_optimizer.masks import read_option_pool

from .model import SolveResult, SolveError, validate_result


def _decode(raw: dict) -> SolveResult:
    return SolveResult(raw["schema_version"], raw["algorithm_version"], raw["pool_digest"], raw["family_digest"],
                       raw["revision_digest"], raw["profile_sha256"], raw["scope_digest"], raw["model_digest"],
                       tuple(tuple(item) for item in raw["assignment"]), tuple(raw["selected_mask_ids"]),
                       raw["selected_mask_count"], raw["lower_bound"], raw["bound_scope"], raw["status"],
                       raw["stop_reason"], raw["digest"])


def _inputs(pool_path: Path, profile):
    pool_path = Path(pool_path)
    pool = read_option_pool(pool_path)
    families = read_family_set(pool_path.with_name("families.json"))
    if getattr(profile, "profile_sha256", None) != pool.profile_sha256:
        raise SolveError("profile identity does not match option pool")
    return pool, families


def write_solve_result(result: SolveResult, path: Path, *, pool_path: Path, profile) -> None:
    pool, families = _inputs(pool_path, profile)
    validate_result(result, pool, families, mask_cap=getattr(profile, "mask_cap", 64))
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(asdict(result), sort_keys=True, separators=(",", ":")), encoding="utf-8")
    os.replace(temporary, path)


def read_solve_result(path: Path, *, pool_path: Path, profile) -> SolveResult:
    try:
        result = _decode(json.loads(Path(path).read_text(encoding="utf-8")))
        pool, families = _inputs(pool_path, profile)
        validate_result(result, pool, families, mask_cap=getattr(profile, "mask_cap", 64))
        return result
    except (OSError, KeyError, TypeError, json.JSONDecodeError, SolveError) as error:
        if isinstance(error, SolveError):
            raise
        raise SolveError(f"invalid solve result: {path}") from error
