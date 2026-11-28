"""Directly analyze the locked text dump into immutable Task 9 artifacts.

This command does not start VPinMAME, ColorizingDMD, or any recorder.  It
parses only the supplied static dump and stores an independent local corpus.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

# `uv run python scripts/...` does not apply pytest's pythonpath setting.
ROOT = Path(__file__).resolve().parents[1]
for location in (ROOT, ROOT / "src"):
    if str(location) not in sys.path:
        sys.path.insert(0, str(location))

from dmd_optimizer.capture.text_dump import read_dump
from dmd_optimizer.corpus import Capture, append_capture, read_capture_metadata, read_revision
from dmd_optimizer.explore.coverage import summarize
from dmd_optimizer.families import infer, write_family_set
from dmd_optimizer.masks import generate, write_option_pool
from scripts import lock_profile


def main() -> int:
    parser = argparse.ArgumentParser()
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--dump", type=Path, help="locked static twst_405.txt input")
    source.add_argument("--corpus", type=Path, help="already-imported immutable corpus")
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    output = args.output.resolve()
    record, profile_sha256 = lock_profile._read_profile()
    profile_record = dict(record)
    profile_record.pop("schema_version")
    profile_record.pop("lock_scopes")
    profile_record["rom_members"] = tuple(lock_profile.RomMember(**member) for member in profile_record["rom_members"])
    profile = lock_profile.Profile(**profile_record, profile_sha256=profile_sha256)
    output.mkdir(parents=True, exist_ok=True)
    if args.dump is not None:
        dump = args.dump.resolve()
        source_sha256 = hashlib.file_digest(dump.open("rb"), "sha256").hexdigest()
        if source_sha256 != record["dump_sha256"]:
            raise SystemExit("locked dump SHA-256 does not match profiles/twst_405.json")
        corpus = output / "corpus"
        capture = Capture(source_sha256, str(dump), "ColorizingDMD", None, {}, True,
                          profile.width, profile.height, profile.native_shades, "native-u8", "identity-v1",
                          profile.dump_format["tick_unit"], profile.dump_format, profile.rom_sha256, profile_sha256)
        revision = append_capture(corpus, capture, read_dump(dump, profile))
    else:
        corpus = args.corpus.resolve()
        revision = read_revision(corpus)
        metadata = read_capture_metadata(corpus, revision.digest)
        if len(metadata) != 1 or metadata[0].source.source_sha256 != record["dump_sha256"]:
            raise SystemExit("corpus does not contain the locked dump revision")
        source_sha256 = metadata[0].source.source_sha256
    coverage = summarize(corpus, revision.digest, output / "coverage.checkpoint.json", lambda: False)
    if coverage is None:
        raise SystemExit("coverage did not complete")
    families = infer(revision, (), project=corpus, coverage=coverage)
    write_family_set(families, output / "families.json")
    pool = generate(families, revision, profile, project=corpus)
    write_option_pool(pool, output / "options.json")
    (output / "summary.json").write_text(json.dumps({
        "source_sha256": source_sha256, "revision_digest": revision.digest,
        "family_digest": families.digest, "pool_digest": pool.digest,
        "occurrence_count": revision.occurrence_count, "unique_frame_count": revision.unique_frame_count,
        "repeat_count": coverage.repeat_count, "family_count": len(families.families),
        "option_count": len(pool.options), "families_without_options": list(pool.families_without_options),
    }, sort_keys=True, separators=(",", ":")), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
