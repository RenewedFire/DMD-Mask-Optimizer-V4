"""Run one bounded native ColorizingDMD import or save of the locked TXT dump."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for location in (ROOT, ROOT / "src"):
    if str(location) not in sys.path:
        sys.path.insert(0, str(location))

from dmd_optimizer.adapters.editor import serialize_dump_import_request, stage_editor
from scripts.solve_mask_assignment import _profile


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dump", required=True, type=Path)
    parser.add_argument("--expected-import-count", type=int, default=10_301)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--deadline-ms", type=int, default=60_000)
    parser.add_argument("--operation", choices=("import", "save", "reopen-export"), default="import")
    parser.add_argument("--project", type=Path,
                        help="existing project folder; required only for reopen-export")
    args = parser.parse_args()
    if args.deadline_ms <= 0:
        parser.error("--deadline-ms must be positive")
    output = args.output.resolve()
    if output.exists():
        parser.error(f"refusing to overwrite existing probe output: {output}")
    if (args.operation == "reopen-export") != (args.project is not None):
        parser.error("--project is required only for --operation reopen-export")

    profile = _profile()
    output.mkdir(parents=True)
    decoder = profile.components["bundled decoder"]
    decoder_path = Path(decoder["provenance"]["installation_path"]) / Path(decoder["binary"]).name
    staged_editor = stage_editor(
        Path(profile.components["ColorizingDMD editor"]["provenance"]["installation_path"]),
        output / "editor", profile,
        decoder_path=decoder_path,
    )
    config = output / "editor-config"
    config.mkdir()
    project = args.project.resolve() if args.project else output / "project"
    request = serialize_dump_import_request(
        project, args.dump, args.expected_import_count, profile,
        editor_root=staged_editor, config_root=config, deadline_ms=args.deadline_ms,
    )
    request_data = json.loads(request)
    (output / "request-metadata.json").write_text(json.dumps({
        "dump_path": request_data["dump_path"], "dump_sha256": request_data["dump_sha256"],
        "expected_import_count": request_data["expected_import_count"],
        "request_bytes": len(request.encode("utf-8")), "deadline_ms": args.deadline_ms,
    }, sort_keys=True), encoding="utf-8")
    bridge = ROOT / "build" / "editor_bridge.exe"
    try:
        completed = subprocess.run(
            [str(bridge), f"--{args.operation}-probe"], input=request.encode("utf-8"), capture_output=True,
            timeout=args.deadline_ms / 1000 + 20, check=False,
        )
    except subprocess.TimeoutExpired as error:
        (output / "bridge.stdout").write_bytes(error.stdout or b"")
        (output / "bridge.stderr").write_bytes(error.stderr or b"")
        (output / "result.json").write_text(json.dumps({"status": "aborted", "reason": "wrapper timeout"}), encoding="utf-8")
        return 124
    (output / "bridge.stdout").write_bytes(completed.stdout)
    (output / "bridge.stderr").write_bytes(completed.stderr)
    try:
        response = json.loads(completed.stdout)
    except json.JSONDecodeError:
        response = {"status": "invalid-response"}
    (output / "result.json").write_text(json.dumps({
        "process_exit_code": completed.returncode, "response": response,
    }, indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps(response, indent=2, sort_keys=True))
    return completed.returncode


if __name__ == "__main__":
    raise SystemExit(main())
