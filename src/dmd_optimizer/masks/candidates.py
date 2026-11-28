from __future__ import annotations
import hashlib, zlib
from dataclasses import replace
from .model import MaskOption, OptionPool, Rejection, option_pool_digest

def _digest(value: bytes) -> str: return hashlib.sha256(value).hexdigest()
def _compared(frame: bytes, ignore: bytes | None) -> bytes: return frame if ignore is None else bytes(value for value, masked in zip(frame, ignore) if not masked)
def _mask_id(ignore: bytes, width: int, height: int) -> str:
    return _digest(width.to_bytes(4, "big") + height.to_bytes(4, "big") + ignore)

def check_candidate(family, reference: bytes, ignore: bytes | None, negatives: tuple[bytes,...], *, width: int, height: int, native_shades: int):
    size = width * height
    if len(reference) != size or any(value >= native_shades for value in reference): raise ValueError("invalid reference")
    if ignore is not None and (len(ignore) != size or any(value > 1 for value in ignore)): return Rejection(family.family_id, None, "invalid-bitmap", None, None, None, None)
    if ignore is not None and not any(ignore): ignore = None
    mask_id = None if ignore is None else _mask_id(ignore, width, height)
    masked = bytes(size) if ignore is None else ignore
    if any(masked[index] for index in family.must_compare): return Rejection(family.family_id, mask_id, "must-compare-violation", None, None, None, None)
    for index in family.required_ignore:
        if not masked[index]: return Rejection(family.family_id, mask_id, "positive-variability", None, None, None, None)
    expected = _compared(reference, ignore); crc = zlib.crc32(expected) & 0xffffffff
    for positive in family.domain_pixels:
        if _compared(positive, ignore) != expected: return Rejection(family.family_id, mask_id, "positive-variability", _digest(positive), crc, zlib.crc32(_compared(positive, ignore)) & 0xffffffff, positive)
    for negative in negatives:
        candidate = _compared(negative, ignore); actual = zlib.crc32(candidate) & 0xffffffff
        if candidate == expected: return Rejection(family.family_id, mask_id, "equal-compared-bytes", _digest(negative), crc, actual, negative)
        if actual == crc: return Rejection(family.family_id, mask_id, "crc-collision", _digest(negative), crc, actual, negative)
    domain = _digest(b"".join(family.domain_pixels))
    option_id = _digest((family.family_id + (mask_id or "unmasked") + domain).encode())
    return MaskOption(option_id, family.family_id, family.reference_frame_id, mask_id, ignore, crc, False, len(family.domain_pixels), len(negatives), domain)

def generate(families, revision, profile, *, project=None, existing_masks=()):
    if families.revision_digest != revision.digest or families.profile_sha256 != profile.profile_sha256:
        raise ValueError("family identity does not match revision/profile")
    if families.schema_version != 1 or families.algorithm_version != "finite-families-v1":
        raise ValueError("unsupported family manifest")
    size = profile.width * profile.height
    for family in families.families:
        if not family.domain_pixels or any(len(pixels) != size or any(value >= profile.native_shades for value in pixels) for pixels in family.domain_pixels):
            raise ValueError("family domain does not match profile")
        if (set(family.required_ignore) & set(family.must_compare)
                or any(index < 0 or index >= size for index in (*family.required_ignore, *family.must_compare))):
            raise ValueError("family pixel partition is invalid")
    if project is not None:
        from dmd_optimizer.corpus import iter_occurrences, read_frames, read_revision
        from dmd_optimizer.families.model import OccurrenceKey

        if read_revision(project, revision.digest) != revision:
            raise ValueError("project revision does not match requested revision")
        rows = tuple(iter_occurrences(project, revision.digest))
        assignments = dict(families.assignments)
        family_by_id = {family.family_id: family for family in families.families}
        expected_keys = {OccurrenceKey(row.capture_id, row.index) for row in rows}
        if set(assignments) != expected_keys or any(target not in family_by_id for target in assignments.values()):
            raise ValueError("family assignments do not cover the corpus scope")
        pixels = read_frames(project, (row.frame_id for row in rows))
        for row in rows:
            family = family_by_id[assignments[OccurrenceKey(row.capture_id, row.index)]]
            if pixels[row.frame_id] not in family.domain_pixels:
                raise ValueError("family domain does not cover assigned corpus frame")
    options, rejections, missing = [], [], []
    ordered_families = tuple(sorted(families.families, key=lambda item: item.family_id))
    all_domains = {family.family_id: tuple(family.domain_pixels) for family in ordered_families}
    total_inputs = sum(len(domain) for domain in all_domains.values())
    required_masks = []
    for item in ordered_families:
        bitmap = bytearray(size)
        for index in item.required_ignore:
            bitmap[index] = 1
        if any(bitmap):
            required_masks.append(bytes(bitmap))

    def union(left: bytes, right: bytes) -> bytes:
        return bytes(bool(a or b) for a, b in zip(left, right))

    seeds = tuple(sorted(dict.fromkeys((*existing_masks, *required_masks)), key=lambda item: _mask_id(item, profile.width, profile.height)))
    pairs = []
    for offset, left in enumerate(seeds):
        for right in seeds[offset + 1:]:
            pairs.append(union(left, right))
            if len(pairs) == 256:
                break
        if len(pairs) == 256:
            break
    triples = []
    for pair in pairs:
        for seed in seeds:
            triples.append(union(pair, seed))
            if len(triples) == 64:
                break
        if len(triples) == 64:
            break
    candidates = tuple(dict.fromkeys((*seeds, *pairs, *triples)))
    full_crc_index: dict[int, list[tuple[str, bytes]]] = {}
    for family_id, domain in all_domains.items():
        for pixels in domain:
            full_crc_index.setdefault(zlib.crc32(pixels) & 0xffffffff, []).append((family_id, pixels))
    for family in ordered_families:
        masks = (None, *candidates)
        accepted = False
        for ignore in dict.fromkeys(masks):
            if ignore is None:
                result = check_candidate(family, family.domain_pixels[0], None, (), width=profile.width, height=profile.height, native_shades=profile.native_shades)
                if not isinstance(result, Rejection):
                    for owner, pixels in full_crc_index[result.crc32]:
                        if owner == family.family_id:
                            continue
                        reason = "equal-compared-bytes" if pixels == family.domain_pixels[0] else "crc-collision"
                        result = Rejection(family.family_id, None, reason, _digest(pixels), result.crc32, result.crc32, pixels)
                        break
                    if not isinstance(result, Rejection):
                        result = replace(result, negative_count=total_inputs - len(family.domain_pixels))
            else:
                negatives = tuple(pixel for key, domain in all_domains.items() if key != family.family_id for pixel in domain)
                result = check_candidate(family, family.domain_pixels[0], ignore, negatives, width=profile.width, height=profile.height, native_shades=profile.native_shades)
            if isinstance(result, Rejection): rejections.append(result)
            else: options.append(result); accepted = True
        if not accepted: missing.append(family.family_id)
    scope = _digest(b"".join(pixel for domain in all_domains.values() for pixel in domain))
    semantic = "|".join(option.option_id for option in options).encode()
    draft = OptionPool(1, "mask-candidates-v1", revision.digest, families.digest, profile.profile_sha256, scope, (256,64), tuple(options), tuple(rejections), tuple(missing), True, "")
    return replace(draft, digest=option_pool_digest(draft))
