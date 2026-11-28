"""Solve one immutable Task 9 candidate pool without replaying a dump."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for location in (ROOT, ROOT / "src"):
    if str(location) not in sys.path:
        sys.path.insert(0, str(location))

from dmd_optimizer.families import read_family_set
from dmd_optimizer.masks import read_option_pool
from dmd_optimizer.solve import solve, write_solve_result
from scripts import lock_profile


class NeverStop:
    def stopped(self) -> bool:
        return False


def _profile():
    record, digest = lock_profile._read_profile()
    record = dict(record)
    record.pop("schema_version")
    record.pop("lock_scopes")
    record["rom_members"] = tuple(lock_profile.RomMember(**item) for item in record["rom_members"])
    return lock_profile.Profile(**record, profile_sha256=digest)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pool", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--time-limit-seconds", type=float, default=30.0)
    args = parser.parse_args()
    pool_path, output = args.pool.resolve(), args.output.resolve()
    profile = _profile()
    pool = read_option_pool(pool_path)
    families = read_family_set(pool_path.with_name("families.json"))
    result = solve(pool, profile, NeverStop(), families=families, time_limit_seconds=args.time_limit_seconds)
    output.mkdir(parents=True, exist_ok=True)
    result_path = output / "solution.json"
    write_solve_result(result, result_path, pool_path=pool_path, profile=profile)
    (output / "summary.json").write_text(json.dumps({
        "revision_digest": result.revision_digest, "family_digest": result.family_digest,
        "pool_digest": result.pool_digest, "solution_digest": result.digest,
        "status": result.status, "selected_mask_count": result.selected_mask_count,
        "lower_bound": result.lower_bound, "bound_scope": result.bound_scope,
        "assignment_count": len(result.assignment), "mask_cap": getattr(profile, "mask_cap", 64),
    }, sort_keys=True, separators=(",", ":")), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
