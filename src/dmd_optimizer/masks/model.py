from __future__ import annotations
from dataclasses import dataclass
import hashlib
import json

@dataclass(frozen=True)
class MaskOption:
    option_id: str; family_id: str; reference_frame_id: str; mask_id: str | None; ignore: bytes | None; crc32: int; shape: bool; positive_count: int; negative_count: int; domain_digest: str

@dataclass(frozen=True)
class Rejection:
    family_id: str; mask_id: str | None; reason: str; input_digest: str | None; expected_crc: int | None; actual_crc: int | None; witness_pixels: bytes | None

@dataclass(frozen=True)
class OptionPool:
    schema_version: int; algorithm_version: str; revision_digest: str; family_digest: str; profile_sha256: str; scope_digest: str; generation_limits: tuple[int,int]; options: tuple[MaskOption,...]; rejections: tuple[Rejection,...]; families_without_options: tuple[str,...]; search_complete: bool; digest: str


def option_pool_digest(pool: OptionPool) -> str:
    """Digest the semantic pool fields, excluding the self-referential digest."""
    def encode(value):
        if isinstance(value, bytes):
            return {"bytes": value.hex()}
        if isinstance(value, tuple):
            return [encode(item) for item in value]
        if hasattr(value, "__dataclass_fields__"):
            return {key: encode(getattr(value, key)) for key in value.__dataclass_fields__}
        return value

    payload = encode(pool)
    payload.pop("digest")
    return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()
