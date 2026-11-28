"""Record a bounded, static-input controller qualification."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
from dataclasses import asdict, replace
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from dmd_optimizer.controller.model import InputIdentity, RunRequest
from dmd_optimizer.controller.run import JobStages, StageOutcome, run_job


class _Clock:
    def monotonic(self) -> float:
        return time.monotonic()


class _Stop:
    def stopped(self) -> bool:
        return False


def _sha256(path: Path) -> str:
    with path.open("rb") as source:
        return hashlib.file_digest(source, "sha256").hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--corpus", required=True, type=Path)
    parser.add_argument("--solution", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--budget-seconds", default=1800, type=float)
    parser.add_argument("--prior-run", type=Path)
    args = parser.parse_args()
    corpus, solution = args.corpus.resolve(), args.solution.resolve()
    if not corpus.is_file() or not solution.is_file():
        parser.error("--corpus and --solution must name existing files")
    document = json.loads(solution.read_text(encoding="utf-8"))
    profile = document.get("profile_sha256")
    revision = document.get("revision_digest")
    if not isinstance(profile, str) or not isinstance(revision, str):
        parser.error("solution lacks immutable profile or revision identity")
    identity = InputIdentity(_sha256(solution), profile, _sha256(corpus),
                             (("bounded-controller", "v1"), ("solution-revision", revision)))
    stages = JobStages(identity=identity, publish=lambda deadline: StageOutcome(export_status="diagnostic-only"))
    result = run_job(RunRequest(solution, (), args.output.resolve(), args.budget_seconds, args.prior_run),
                     _Clock(), _Stop(), stages=stages)
    result = replace(result, diagnostics={**result.diagnostics, "static_input": True,
                                         "corpus_sha256": identity.corpus_revision,
                                         "solution_sha256": identity.rom_sha256})
    print(json.dumps(asdict(result), sort_keys=True, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
