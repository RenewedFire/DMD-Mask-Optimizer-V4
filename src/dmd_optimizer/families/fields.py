"""Finite, explicitly evidenced text-field rendering."""

from __future__ import annotations

from .model import FieldSpec


class FieldError(ValueError):
    pass


def _validate(field: FieldSpec, width: int, height: int, native_shades: int) -> dict[str, bytes]:
    x, y, field_width, field_height = field.bounds
    if field.alignment not in {"left", "right"} or field.overflow not in {"reject", "clip"}:
        raise FieldError("unsupported field layout")
    if min(x, y, field_width, field_height, field.glyph_width, field.glyph_height, field.advance) < 0 or not field.values:
        raise FieldError("invalid field geometry or domain")
    if x + field_width > width or y + field_height > height:
        raise FieldError("field exceeds frame geometry")
    glyphs = dict(field.glyphs)
    if len(glyphs) != len(field.glyphs) or any(len(value) != field.glyph_width * field.glyph_height or any(shade >= native_shades for shade in value) for value in glyphs.values()):
        raise FieldError("invalid glyph pixels")
    if any(character not in glyphs for value in field.values for character in value):
        raise FieldError("field values use unsupported glyph")
    return glyphs


def render_domain(template: bytes, fields: tuple[FieldSpec, ...], joint_values: tuple[tuple[str, ...], ...], *, width: int, height: int, native_shades: int) -> tuple[bytes, ...]:
    if len(template) != width * height or any(shade >= native_shades for shade in template):
        raise FieldError("template pixels do not match geometry")
    if not fields or not joint_values or any(len(values) != len(fields) for values in joint_values):
        raise FieldError("invalid joint field domain")
    if len(joint_values) > 4_096 or len(joint_values) * width * height > 64 * 1024 * 1024:
        raise FieldError("domain budget exceeded")
    glyphs = [_validate(field, width, height, native_shades) for field in fields]
    occupied = set()
    for field in fields:
        x, y, field_width, field_height = field.bounds
        pixels = {(row * width + column) for row in range(y, y + field_height) for column in range(x, x + field_width)}
        if occupied & pixels:
            raise FieldError("field bounds overlap")
        occupied |= pixels
    rendered = []
    for values in joint_values:
        output = bytearray(template)
        for field, value, characters in zip(fields, values, glyphs):
            if value not in field.values:
                raise FieldError("joint value outside declared domain")
            x, y, field_width, field_height = field.bounds
            for row in range(y, y + field_height):
                output[row * width + x:row * width + x + field_width] = b"\0" * field_width
            extent = len(value) * field.advance
            if extent > field_width and field.overflow == "reject":
                raise FieldError("field value exceeds bounds")
            start = x if field.alignment == "left" else x + max(0, field_width - extent)
            for number, character in enumerate(value):
                glyph = characters[character]
                for glyph_y in range(field.glyph_height):
                    for glyph_x in range(field.glyph_width):
                        target_x = start + number * field.advance + glyph_x
                        target_y = y + glyph_y
                        if x <= target_x < x + field_width and y <= target_y < y + field_height:
                            output[target_y * width + target_x] = glyph[glyph_y * field.glyph_width + glyph_x]
        rendered.append(bytes(output))
    return tuple(rendered)
