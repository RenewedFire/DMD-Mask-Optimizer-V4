"""Append-only checkpoint files with identity validation and fallback."""

import hashlib
import json
import os
from dataclasses import asdict
from pathlib import Path

from .model import InputIdentity, JobState


class CheckpointError(ValueError):
    pass


def _canonical(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def _payload(state: JobState) -> dict:
    return {"schema_version": 1, "state": asdict(state)}


def _decode(path: Path) -> tuple[str, JobState]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        digest = value.pop("sha256")
        if hashlib.sha256(_canonical(value)).hexdigest() != digest:
            raise CheckpointError("checkpoint checksum mismatch")
        state = value["state"]
        identity = state["identity"]
        return digest, JobState(
            InputIdentity(identity["rom_sha256"], identity["profile_sha256"], identity["corpus_revision"],
                          tuple(tuple(item) for item in identity["algorithms"]), identity.get("native_export_sha256")),
            state.get("last_verified_revision"), state.get("export_revision"),
            tuple(state.get("pending_frames", ())), dict(state.get("statuses", {})),
        )
    except (OSError, KeyError, TypeError, json.JSONDecodeError) as error:
        raise CheckpointError("checkpoint is malformed") from error


def save_checkpoint(run_dir: Path, state: JobState) -> str:
    run_dir = Path(run_dir)
    run_dir.mkdir(parents=True, exist_ok=True)
    existing = sorted(run_dir.glob("checkpoint-*.json"))
    number = 1 if not existing else int(existing[-1].stem.rsplit("-", 1)[1]) + 1
    payload = _payload(state)
    digest = hashlib.sha256(_canonical(payload)).hexdigest()
    document = {**payload, "sha256": digest}
    target = run_dir / f"checkpoint-{number:06d}.json"
    temporary = target.with_suffix(".tmp")
    temporary.write_bytes(_canonical(document))
    os.replace(temporary, target)
    return digest


def load_checkpoint(run_dir: Path, expected: InputIdentity) -> JobState:
    errors: list[str] = []
    for path in reversed(sorted(Path(run_dir).glob("checkpoint-*.json"))):
        try:
            _, state = _decode(path)
        except CheckpointError as error:
            errors.append(str(error))
            continue
        if state.identity != expected:
            raise CheckpointError("checkpoint identity mismatch")
        return state
    detail = errors[0] if errors else "checkpoint not found"
    raise CheckpointError(detail)
