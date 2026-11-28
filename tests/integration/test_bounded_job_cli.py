import json
import subprocess
import sys
from pathlib import Path


def test_bounded_job_cli_records_fixed_input_identity_without_live_processes(tmp_path):
    root = Path(__file__).resolve().parents[2]
    corpus = tmp_path / "corpus.sqlite3"
    corpus.write_bytes(b"static-corpus")
    solution = tmp_path / "solution.json"
    solution.write_text(json.dumps({"revision_digest": "a" * 64, "profile_sha256": "b" * 64}), encoding="utf-8")
    output = tmp_path / "runs"
    completed = subprocess.run(
        [sys.executable, "scripts/run_bounded_job.py", "--corpus", str(corpus), "--solution", str(solution),
         "--output", str(output), "--budget-seconds", "1"], cwd=root, text=True, capture_output=True, check=False)
    assert completed.returncode == 0, completed.stderr
    result = json.loads(completed.stdout)
    assert result["export_status"] == "diagnostic-only"
    assert result["last_verified_revision"] is None
    assert result["diagnostics"]["static_input"] is True
    assert (output / result["run_id"] / "checkpoint-000001.json").is_file()


def test_bounded_job_cli_uses_a_fresh_run_directory_each_time(tmp_path):
    root = Path(__file__).resolve().parents[2]
    corpus = tmp_path / "corpus.sqlite3"
    corpus.write_bytes(b"static-corpus")
    solution = tmp_path / "solution.json"
    solution.write_text(json.dumps({"revision_digest": "a" * 64, "profile_sha256": "b" * 64}), encoding="utf-8")
    output = tmp_path / "runs"
    command = [sys.executable, "scripts/run_bounded_job.py", "--corpus", str(corpus), "--solution", str(solution),
               "--output", str(output), "--budget-seconds", "1"]
    first = json.loads(subprocess.run(command, cwd=root, text=True, capture_output=True, check=True).stdout)
    second = json.loads(subprocess.run(command, cwd=root, text=True, capture_output=True, check=True).stdout)
    assert first["run_id"] != second["run_id"]
    assert (output / first["run_id"] / "checkpoint-000001.json").is_file()
    assert (output / second["run_id"] / "checkpoint-000001.json").is_file()
