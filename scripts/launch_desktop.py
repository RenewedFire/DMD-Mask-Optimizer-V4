"""Launch or inspect the local desktop authoring workflow."""

from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))


def readiness() -> dict[str, object]:
    corpus = ROOT / "twst_405.txt"
    return {
        "pyside6_available": importlib.util.find_spec("PySide6") is not None,
        "fixed_corpus_available": corpus.is_file(),
        "fixed_corpus_path": str(corpus),
        "profile": "twst_405",
        "external_apps_required": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    if args.check:
        print(json.dumps(readiness(), sort_keys=True))
        return 0
    from dmd_optimizer.ui.main import launch_desktop
    return launch_desktop()


if __name__ == "__main__":
    raise SystemExit(main())
