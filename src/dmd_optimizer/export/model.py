from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ExportDecision:
    revision_digest: str
    pool_digest: str
    family_digest: str
    solution_digest: str
    requested_reference_count: int
    representable_reference_count: int
    custom_mask_count: int
    bridge_request_bytes: int
    bridge_limit_bytes: int
    runtime_reference_limit: int
    full_export_possible: bool
    reasons: tuple[str, ...]
