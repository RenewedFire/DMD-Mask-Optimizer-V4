"""Immutable contracts for selecting Task 9 candidate options."""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, is_dataclass


class SolveError(ValueError):
    pass


@dataclass(frozen=True)
class SolveResult:
    schema_version: int
    algorithm_version: str
    pool_digest: str
    family_digest: str
    revision_digest: str
    profile_sha256: str
    scope_digest: str
    model_digest: str
    assignment: tuple[tuple[str, str], ...]
    selected_mask_ids: tuple[str, ...]
    selected_mask_count: int | None
    lower_bound: int | None
    bound_scope: str
    status: str
    stop_reason: str | None
    digest: str


def _jsonable(value):
    if isinstance(value, bytes):
        return {"bytes": value.hex()}
    if is_dataclass(value):
        return {key: _jsonable(item) for key, item in asdict(value).items()}
    if isinstance(value, tuple):
        return [_jsonable(item) for item in value]
    return value


def result_digest(result: SolveResult) -> str:
    payload = _jsonable(result)
    payload.pop("digest")
    return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()


def solve_model_digest(pool, mask_cap: int) -> str:
    """Identity of the precise candidate-pool model used by the solver."""
    payload = {
        "algorithm": "mask-cover-v1",
        "objective": "mask-count-then-option-id-rank-v1",
        "pool": pool.digest,
        "mask_cap": mask_cap,
        "options": [
            (item.option_id, item.family_id, item.mask_id)
            for item in sorted(pool.options, key=lambda item: item.option_id)
        ],
    }
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def validate_result(result: SolveResult, pool, families, *, mask_cap: int) -> None:
    if result.schema_version != 1 or result.algorithm_version != "mask-cover-v1":
        raise SolveError("unsupported solve result")
    if result.pool_digest != pool.digest:
        raise SolveError("pool identity mismatch")
    if (result.family_digest, result.revision_digest, result.profile_sha256, result.scope_digest) != (families.digest, pool.revision_digest, pool.profile_sha256, pool.scope_digest):
        raise SolveError("family or scope identity mismatch")
    if result.model_digest != solve_model_digest(pool, mask_cap):
        raise SolveError("model identity mismatch")
    if result.bound_scope != "candidate-pool" or result.digest != result_digest(result):
        raise SolveError("invalid result digest or bound scope")
    valid_status = {"optimal-pool", "feasible-unproved", "infeasible-pool", "no-feasible-option", "unknown"}
    if result.status not in valid_status:
        raise SolveError("invalid result status")
    family_ids = {family.family_id for family in families.families}
    if pool.families_without_options and result.status not in {"no-feasible-option", "infeasible-pool"}:
        raise SolveError("pool has families without options")
    if result.status in {"optimal-pool", "feasible-unproved"}:
        assigned = [family_id for family_id, _ in result.assignment]
        if len(assigned) != len(set(assigned)) or set(assigned) != family_ids:
            raise SolveError("assignment must contain each family exactly once")
        options = {option.option_id: option for option in pool.options}
        if any(option_id not in options or options[option_id].family_id != family_id for family_id, option_id in result.assignment):
            raise SolveError("assignment contains invalid option")
        masks = tuple(sorted({options[option_id].mask_id for _, option_id in result.assignment if options[option_id].mask_id is not None}))
        if result.selected_mask_ids != masks or result.selected_mask_count != len(masks):
            raise SolveError("selected mask count does not match assignment")
        if result.selected_mask_count > mask_cap:
            raise SolveError("mask cap exceeded")
        if result.status == "optimal-pool" and result.lower_bound != result.selected_mask_count:
            raise SolveError("optimal result must prove its selected mask count")
    elif result.assignment or result.selected_mask_ids or result.selected_mask_count is not None:
        raise SolveError("non-feasible result contains an assignment")
    if result.status == "no-feasible-option":
        family_ids_with_options = {item.family_id for item in pool.options}
        if not pool.families_without_options and family_ids <= family_ids_with_options:
            raise SolveError("no-feasible-option result has no missing family domain")
    if result.status == "infeasible-pool":
        raise SolveError("infeasible result requires an external certificate")
    if result.lower_bound is not None and (result.lower_bound < 0 or result.selected_mask_count is not None and result.lower_bound > result.selected_mask_count):
        raise SolveError("invalid lower bound")
