from dataclasses import dataclass, replace


@dataclass
class Clock:
    now: float = 0.0
    def monotonic(self): return self.now


class Stop:
    def stopped(self): return False


def identity(profile="b"):
    from dmd_optimizer.controller.model import InputIdentity
    return InputIdentity("a" * 64, profile * 64, "c" * 64, (("solver", "v1"),))


def request(tmp_path, name, prior=None):
    from dmd_optimizer.controller.model import RunRequest
    return RunRequest(tmp_path / "twst_405.zip", (), tmp_path / name, prior_run=prior)


def test_compatible_resume_keeps_verified_scope_under_new_budget(tmp_path):
    from dmd_optimizer.controller.run import JobStages, StageOutcome, run_job

    initial = run_job(request(tmp_path, "first"), Clock(), Stop(), stages=JobStages(
        baseline=lambda deadline: StageOutcome(verified_revision="verified"), identity=identity()))
    resumed = run_job(request(tmp_path, "second", tmp_path / "first" / initial.run_id), Clock(), Stop(),
                      stages=JobStages(identity=identity()))
    assert resumed.last_verified_revision == "verified"
    assert resumed.diagnostics["resume"] == "compatible"


def test_identity_change_invalidates_prior_hints_without_mutating_old_run(tmp_path):
    from dmd_optimizer.controller.run import JobStages, StageOutcome, run_job

    initial = run_job(request(tmp_path, "first"), Clock(), Stop(), stages=JobStages(
        baseline=lambda deadline: StageOutcome(verified_revision="verified"), identity=identity()))
    prior = tmp_path / "first" / initial.run_id
    before = {path.name: path.read_bytes() for path in prior.glob("checkpoint-*.json")}
    resumed = run_job(request(tmp_path, "second", prior), Clock(), Stop(), stages=JobStages(identity=identity("d")))
    assert resumed.last_verified_revision is None
    assert resumed.diagnostics["resume"] == "identity-mismatch"
    assert {path.name: path.read_bytes() for path in prior.glob("checkpoint-*.json")} == before
