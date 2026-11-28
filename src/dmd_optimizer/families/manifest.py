"""Canonical family-set publication for the next optimization stage."""

from __future__ import annotations

import json
import os
from dataclasses import asdict
from pathlib import Path

from .infer import _ALGORITHM, _digest
from .model import Family, FamilySet, OccurrenceKey


class ManifestError(ValueError):
    pass


def _jsonable(value):
    if isinstance(value, bytes):
        return {"bytes": value.hex()}
    if isinstance(value, tuple):
        return [_jsonable(item) for item in value]
    if isinstance(value, list):
        return [_jsonable(item) for item in value]
    if isinstance(value, dict):
        return {key: _jsonable(item) for key, item in value.items()}
    return value


def _payload(value: FamilySet) -> dict:
    return _jsonable(asdict(value))


def write_family_set(families: FamilySet, path: Path) -> None:
    payload = _payload(families)
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False), encoding="utf-8")
    os.replace(temporary, path)


def _bytes(value) -> bytes:
    if not isinstance(value, dict) or set(value) != {"bytes"} or not isinstance(value["bytes"], str):
        raise ManifestError("invalid byte payload")
    try:
        return bytes.fromhex(value["bytes"])
    except ValueError as error:
        raise ManifestError("invalid byte payload") from error


def read_family_set(path: Path) -> FamilySet:
    try:
        raw = json.loads(Path(path).read_text(encoding="utf-8"))
        if raw.get("schema_version") != 1:
            raise ManifestError("unsupported family manifest schema")
        if raw.get("algorithm_version") != _ALGORITHM:
            raise ManifestError("unsupported family manifest algorithm")
        families = tuple(Family(
            item["family_id"], item["status"], item["context"], item["layout_id"], item["animation_state"],
            item["reference_frame_id"], tuple(item["observed_frame_ids"]), tuple(_bytes(pixel) for pixel in item["domain_pixels"]),
            tuple(item["required_ignore"]), tuple(item["must_compare"]), tuple(item["evidence_ids"]), item["reason"],
        ) for item in raw["families"])
        assignments = tuple((OccurrenceKey(item[0]["capture_id"], item[0]["index"]), item[1]) for item in raw["assignments"])
        result = FamilySet(1, _ALGORITHM, raw["revision_digest"], raw["profile_sha256"], families, assignments,
                           tuple(tuple(item) for item in raw["unresolved"]), raw["digest"])
        identifiers = {item.family_id for item in families}
        if len(identifiers) != len(families):
            raise ManifestError("duplicate family ID")
        if len({key for key, _ in assignments}) != len(assignments) or any(target not in identifiers for _, target in assignments):
            raise ManifestError("invalid family assignment")
        for family in families:
            if not family.domain_pixels or len({len(pixel) for pixel in family.domain_pixels}) != 1:
                raise ManifestError("invalid family domain")
            expected = set(range(len(family.domain_pixels[0])))
            ignored, compared = set(family.required_ignore), set(family.must_compare)
            if ignored & compared or ignored | compared != expected:
                raise ManifestError("invalid family pixel partition")
        semantic = {"schema_version": 1, "algorithm_version": _ALGORITHM, "revision_digest": result.revision_digest,
                    "profile_sha256": result.profile_sha256, "families": result.families, "assignments": result.assignments,
                    "unresolved": result.unresolved}
        if _digest(semantic) != result.digest:
            raise ManifestError("family manifest digest mismatch")
        return result
    except (OSError, KeyError, TypeError, json.JSONDecodeError, ManifestError) as error:
        if isinstance(error, ManifestError):
            raise
        raise ManifestError(f"invalid family manifest: {path}") from error
