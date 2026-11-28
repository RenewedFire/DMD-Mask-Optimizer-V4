"""Deterministic CP-SAT selection over a verified Task 9 option pool."""

from __future__ import annotations

from dataclasses import replace

from ortools.sat.python import cp_model

from .model import SolveResult, result_digest, solve_model_digest, validate_result


def model_digest(pool, mask_cap: int) -> str:
    return solve_model_digest(pool, mask_cap)


def _result(pool, families, cap, status, *, assignment=(), masks=(), lower_bound=None, stop_reason=None):
    draft = SolveResult(1, "mask-cover-v1", pool.digest, families.digest, pool.revision_digest,
                        pool.profile_sha256, pool.scope_digest, model_digest(pool, cap), tuple(assignment),
                        tuple(masks), None if status not in {"optimal-pool", "feasible-unproved"} else len(masks),
                        lower_bound, "candidate-pool", status, stop_reason, "")
    return replace(draft, digest=result_digest(draft))


def _greedy_choice(by_family):
    """Return a deterministic feasible hint, preferring already-active masks."""
    selected, active = {}, set()
    for family_id in sorted(by_family):
        options = sorted(by_family[family_id], key=lambda item: (
            item.mask_id is not None,
            item.mask_id not in active if item.mask_id is not None else False,
            item.mask_id or "",
            item.option_id,
        ))
        choice = options[0]
        selected[family_id] = choice
        if choice.mask_id is not None:
            active.add(choice.mask_id)
    return selected, active


class _StopCallback(cp_model.CpSolverSolutionCallback):
    def __init__(self, stop):
        super().__init__()
        self._stop = stop

    def on_solution_callback(self):
        if self._stop.stopped():
            self.stop_search()


def solve(pool, profile, stop, *, families, time_limit_seconds: float):
    """Select one option per frozen family while minimizing custom bitmaps."""
    cap = getattr(profile, "mask_cap", 64)
    if getattr(profile, "profile_sha256", None) != pool.profile_sha256:
        raise ValueError("profile identity does not match option pool")
    if not isinstance(cap, int) or cap < 0:
        raise ValueError("invalid mask cap")
    family_ids = tuple(sorted(item.family_id for item in families.families))
    by_family = {family_id: [] for family_id in family_ids}
    for option in pool.options:
        if option.family_id in by_family:
            by_family[option.family_id].append(option)
    if pool.families_without_options or any(not by_family[family_id] for family_id in family_ids):
        return _result(pool, families, cap, "no-feasible-option")
    if stop.stopped():
        return _result(pool, families, cap, "unknown", stop_reason="cancelled-before-solve")

    model = cp_model.CpModel()
    choices = {option.option_id: model.new_bool_var(f"option_{offset}") for offset, option in enumerate(sorted(pool.options, key=lambda item: item.option_id))}
    masks = {mask_id: model.new_bool_var(f"mask_{offset}") for offset, mask_id in enumerate(sorted({item.mask_id for item in pool.options if item.mask_id is not None}))}
    for family_id in family_ids:
        model.add_exactly_one(choices[item.option_id] for item in by_family[family_id])
    for option in pool.options:
        if option.mask_id is not None:
            model.add(choices[option.option_id] <= masks[option.mask_id])
    model.add(sum(masks.values()) <= cap)
    # The primary custom-mask count must always dominate the deterministic
    # option-ID tie-breaker.  Runtime/reference costs are unavailable here.
    ordered_options = tuple(sorted(pool.options, key=lambda item: item.option_id))
    tie_cost = {item.option_id: index for index, item in enumerate(ordered_options)}
    maximum_tie_cost = sum(sorted(tie_cost.values(), reverse=True)[:len(family_ids)])
    primary_weight = maximum_tie_cost + 1
    model.minimize(primary_weight * sum(masks.values()) + sum(tie_cost[item.option_id] * choices[item.option_id] for item in ordered_options))

    greedy, greedy_masks = _greedy_choice(by_family)
    if len(greedy_masks) <= cap:
        for option in pool.options:
            model.add_hint(choices[option.option_id], int(greedy[option.family_id].option_id == option.option_id))
        for mask_id, variable in masks.items():
            model.add_hint(variable, int(mask_id in greedy_masks))

    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = max(0.0, time_limit_seconds)
    solver.parameters.num_search_workers = 1
    solver.parameters.random_seed = 0
    status = solver.solve(model, _StopCallback(stop))
    if stop.stopped() and status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        return _result(pool, families, cap, "unknown", stop_reason="cancelled")
    if status == cp_model.INFEASIBLE:
        return _result(pool, families, cap, "infeasible-pool")
    if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        return _result(pool, families, cap, "unknown", stop_reason="time-limit")

    selected = tuple(sorted((option.family_id, option.option_id) for option in pool.options if solver.value(choices[option.option_id])))
    selected_masks = tuple(sorted(mask_id for mask_id, variable in masks.items() if solver.value(variable)))
    optimal = status == cp_model.OPTIMAL and not stop.stopped()
    lower_bound = len(selected_masks) if optimal else max(0, int(solver.best_objective_bound() // primary_weight))
    result = _result(pool, families, cap, "optimal-pool" if optimal else "feasible-unproved",
                     assignment=selected, masks=selected_masks, lower_bound=lower_bound,
                     stop_reason=None if optimal else "cancelled" if stop.stopped() else "time-limit")
    validate_result(result, pool, families, mask_cap=cap)
    return result
