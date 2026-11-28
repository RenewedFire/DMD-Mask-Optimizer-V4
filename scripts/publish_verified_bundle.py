"""Publish a Task 11 diagnostic bundle from immutable Task 9/10 artifacts."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for location in (ROOT, ROOT / "src"):
    if str(location) not in sys.path:
        sys.path.insert(0, str(location))

from dmd_optimizer.corpus.store import read_revision
from dmd_optimizer.export.compile import compile_selection
from dmd_optimizer.export.preflight import preflight
from dmd_optimizer.export.publish import publish_diagnostic
from dmd_optimizer.families import read_family_set
from dmd_optimizer.masks import read_option_pool
from dmd_optimizer.solve import read_solve_result
from scripts.solve_mask_assignment import _profile


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pool", required=True, type=Path)
    parser.add_argument("--solution", required=True, type=Path)
    parser.add_argument("--corpus", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    pool_path = args.pool.resolve()
    profile = _profile()
    pool = read_option_pool(pool_path)
    families = read_family_set(pool_path.with_name("families.json"))
    result = read_solve_result(args.solution.resolve(), pool_path=pool_path, profile=profile)
    revision = read_revision(args.corpus.resolve(), result.revision_digest)
    decision = preflight(result, pool, families, revision_digest=revision.digest)
    selection = compile_selection(result, pool, families, decision, args.corpus.resolve())
    record = publish_diagnostic(selection, args.output.resolve(), reasons=decision.reasons or ("native editor publication not yet qualified",))
    print(json.dumps({"status": record.status, "folder": str(record.folder), "reasons": record.reasons, "mapped_occurrences": len(selection.occurrences), "reference_count": len(selection.references), "full_export_possible": decision.full_export_possible, "bridge_request_bytes": decision.bridge_request_bytes}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
