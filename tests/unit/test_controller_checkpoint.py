from dataclasses import replace

import pytest


def identity():
    from dmd_optimizer.controller.model import InputIdentity
    return InputIdentity(
        rom_sha256="a" * 64,
        profile_sha256="b" * 64,
        corpus_revision="c" * 64,
        algorithms=(("coverage", "v1"), ("solver", "v1")),
    )


def state():
    from dmd_optimizer.controller.model import JobState
    return JobState(identity(), "verified-revision", "verified-export", ("late-frame",), {"status": "diagnostic-only"})


def test_request_defaults_to_thirty_minutes(tmp_path):
    from dmd_optimizer.controller.model import RunRequest
    request = RunRequest(tmp_path / "twst_405.zip", (), tmp_path / "runs")
    assert request.budget_seconds == 1800


def test_checkpoint_round_trips_and_falls_back_from_truncated_newest_generation(tmp_path):
    from dmd_optimizer.controller.checkpoint import load_checkpoint, save_checkpoint

    first = save_checkpoint(tmp_path, state())
    second = save_checkpoint(tmp_path, replace(state(), pending_frames=("late-frame", "later-frame")))
    assert first != second
    newest = max(tmp_path.glob("checkpoint-*.json"))
    newest.write_text("{", encoding="utf-8")
    loaded = load_checkpoint(tmp_path, identity())
    assert loaded.pending_frames == ("late-frame",)


def test_checkpoint_rejects_identity_mismatch_without_mutating_prior_generation(tmp_path):
    from dmd_optimizer.controller.checkpoint import CheckpointError, load_checkpoint, save_checkpoint

    save_checkpoint(tmp_path, state())
    before = {path.name: path.read_bytes() for path in tmp_path.glob("checkpoint-*.json")}
    with pytest.raises(CheckpointError, match="identity"):
        load_checkpoint(tmp_path, replace(identity(), profile_sha256="d" * 64))
    assert {path.name: path.read_bytes() for path in tmp_path.glob("checkpoint-*.json")} == before
