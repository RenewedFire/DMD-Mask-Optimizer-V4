"""Native-resolution DMD preview rendering."""

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QImage


def render_frame(native_pixels: bytes, width: int, height: int, scale: int,
                 ignore_bitmap: bytes | None = None) -> QImage:
    if width <= 0 or height <= 0 or scale <= 0 or len(native_pixels) != width * height:
        raise ValueError("invalid native frame dimensions or pixel payload")
    image = QImage(width, height, QImage.Format.Format_ARGB32)
    shades = (0, 85, 170, 255)
    for index, value in enumerate(native_pixels):
        color = QColor(shades[min(3, value)], shades[min(3, value)], shades[min(3, value)])
        if ignore_bitmap is not None and ignore_bitmap[index]:
            color = QColor(220, 50, 47)
        image.setPixelColor(index % width, index // width, color)
    return image.scaled(width * scale, height * scale, Qt.AspectRatioMode.IgnoreAspectRatio,
                        Qt.TransformationMode.FastTransformation)
