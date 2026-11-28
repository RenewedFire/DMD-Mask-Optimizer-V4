"""Fail-closed capacity and identity gate for editor export."""

from __future__ import annotations

import json

from dmd_optimizer.solve.model import SolveError, validate_result

from .model import ExportDecision

# The full fixed Twister unique-frame import is 86,353,284 bytes.  128 MiB
# remains bounded while allowing that measured request and fixed metadata.
BRIDGE_REQUEST_LIMIT = 128 * 1024 * 1024
RUNTIME_REFERENCE_LIMIT = 65_535
CUSTOM_MASK_LIMIT = 64


class ExportPreflightError(ValueError):
    pass


def _request_bytes(result, pool, families) -> int:
    by_family = {item.family_id: item for item in families.families}
    options = {item.option_id: item for item in pool.options}
    records = []
    for family_id, option_id in result.assignment:
        family = by_family[family_id]
        option = options[option_id]
        pixels = family.domain_pixels[0]
        records.append({
            "id": option.reference_frame_id,
            "native_pixels": list(pixels),
            "source_sha256": __import__("hashlib").sha256(pixels).hexdigest(),
            "ignore_bitmap": None if option.ignore is None else list(option.ignore),
            "ignore_sha256": None if option.ignore is None else __import__("hashlib").sha256(option.ignore).hexdigest(),
            "shape": False,
        })
    # This is the exact JSON shape carried by the bridge's `references`
    # member; fixed request metadata only increases its total size.
    return len(json.dumps({"schema_version": 1, "references": records}, separators=(",", ":")).encode("utf-8"))


def preflight(result, pool, families, *, revision_digest: str, bridge_limit_bytes: int = BRIDGE_REQUEST_LIMIT) -> ExportDecision:
    """Validate a frozen solve handoff and report full-scope export capacity."""
    if bridge_limit_bytes <= 0:
        raise ExportPreflightError("bridge limit must be positive")
    if revision_digest != pool.revision_digest or revision_digest != families.revision_digest:
        raise ExportPreflightError("revision identity mismatch")
    try:
        validate_result(result, pool, families, mask_cap=CUSTOM_MASK_LIMIT)
    except SolveError as error:
        raise ExportPreflightError(str(error)) from error
    requested = len(result.assignment)
    request_bytes = _request_bytes(result, pool, families)
    reasons = []
    if result.selected_mask_count is None:
        reasons.append("solution has no feasible assignment")
    elif result.selected_mask_count > CUSTOM_MASK_LIMIT:
        reasons.append(f"custom-mask limit exceeded: {result.selected_mask_count} > {CUSTOM_MASK_LIMIT}")
    if requested > RUNTIME_REFERENCE_LIMIT:
        reasons.append(f"runtime reference limit exceeded: {requested} > {RUNTIME_REFERENCE_LIMIT}")
    if request_bytes > bridge_limit_bytes:
        reasons.append(f"bridge request limit exceeded: {request_bytes} > {bridge_limit_bytes}")
    possible = not reasons
    return ExportDecision(
        revision_digest, pool.digest, families.digest, result.digest, requested,
        requested if possible else 0, result.selected_mask_count or 0, request_bytes,
        bridge_limit_bytes, RUNTIME_REFERENCE_LIMIT, possible, tuple(reasons),
    )
