"""Pixel-aligned graphical scales composed beneath waterfall history."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Mapping, Protocol

from kiwi_client.waterfall_raster import CURSOR_MARKER_RGB, RasterImage
from kiwi_client.waterfall_terminal import choose_frequency_tick_step, frequency_label_decimals

PASSBAND_SCALE_RGB = (0, 255, 0)
FREQUENCY_SCALE_RGB = (210, 210, 210)
PRESET_SCALE_RGB = (0, 255, 255)

# Dependency-free 5x7 font. Unknown characters use the question-mark glyph.
_FONT = {
    " ": ("00000",) * 7,
    ".": ("00000", "00000", "00000", "00000", "00000", "01100", "01100"),
    "-": ("00000", "00000", "00000", "11111", "00000", "00000", "00000"),
    "?": ("01110", "10001", "00001", "00010", "00100", "00000", "00100"),
    "0": ("01110", "10001", "10011", "10101", "11001", "10001", "01110"),
    "1": ("00100", "01100", "00100", "00100", "00100", "00100", "01110"),
    "2": ("01110", "10001", "00001", "00010", "00100", "01000", "11111"),
    "3": ("11110", "00001", "00001", "01110", "00001", "00001", "11110"),
    "4": ("00010", "00110", "01010", "10010", "11111", "00010", "00010"),
    "5": ("11111", "10000", "10000", "11110", "00001", "00001", "11110"),
    "6": ("01110", "10000", "10000", "11110", "10001", "10001", "01110"),
    "7": ("11111", "00001", "00010", "00100", "01000", "01000", "01000"),
    "8": ("01110", "10001", "10001", "01110", "10001", "10001", "01110"),
    "9": ("01110", "10001", "10001", "01111", "00001", "00001", "01110"),
    "A": ("01110", "10001", "10001", "11111", "10001", "10001", "10001"),
    "B": ("11110", "10001", "10001", "11110", "10001", "10001", "11110"),
    "C": ("01111", "10000", "10000", "10000", "10000", "10000", "01111"),
    "D": ("11110", "10001", "10001", "10001", "10001", "10001", "11110"),
    "E": ("11111", "10000", "10000", "11110", "10000", "10000", "11111"),
    "F": ("11111", "10000", "10000", "11110", "10000", "10000", "10000"),
    "G": ("01111", "10000", "10000", "10111", "10001", "10001", "01111"),
    "H": ("10001", "10001", "10001", "11111", "10001", "10001", "10001"),
    "I": ("01110", "00100", "00100", "00100", "00100", "00100", "01110"),
    "J": ("00111", "00010", "00010", "00010", "10010", "10010", "01100"),
    "K": ("10001", "10010", "10100", "11000", "10100", "10010", "10001"),
    "L": ("10000", "10000", "10000", "10000", "10000", "10000", "11111"),
    "M": ("10001", "11011", "10101", "10101", "10001", "10001", "10001"),
    "N": ("10001", "11001", "10101", "10011", "10001", "10001", "10001"),
    "O": ("01110", "10001", "10001", "10001", "10001", "10001", "01110"),
    "P": ("11110", "10001", "10001", "11110", "10000", "10000", "10000"),
    "Q": ("01110", "10001", "10001", "10001", "10101", "10010", "01101"),
    "R": ("11110", "10001", "10001", "11110", "10100", "10010", "10001"),
    "S": ("01111", "10000", "10000", "01110", "00001", "00001", "11110"),
    "T": ("11111", "00100", "00100", "00100", "00100", "00100", "00100"),
    "U": ("10001", "10001", "10001", "10001", "10001", "10001", "01110"),
    "V": ("10001", "10001", "10001", "10001", "10001", "01010", "00100"),
    "W": ("10001", "10001", "10001", "10101", "10101", "10101", "01010"),
    "X": ("10001", "10001", "01010", "00100", "01010", "10001", "10001"),
    "Y": ("10001", "10001", "01010", "00100", "00100", "00100", "00100"),
    "Z": ("11111", "00001", "00010", "00100", "01000", "10000", "11111"),
}


def bitmap_text_width(text: str, *, scale: int = 1) -> int:
    if scale <= 0:
        raise ValueError("bitmap font scale must be positive")
    return 0 if not text else len(text) * 6 * scale - scale


def draw_bitmap_text(
    rgb: bytearray,
    width: int,
    height: int,
    x: int,
    y: int,
    text: str,
    color: tuple[int, int, int],
    *,
    scale: int = 1,
) -> None:
    """Draw clipped uppercase 5x7 bitmap text into packed RGB storage."""
    if width <= 0 or height <= 0 or len(rgb) != width * height * 3:
        raise ValueError("bitmap canvas dimensions do not match RGB storage")
    if scale <= 0:
        raise ValueError("bitmap font scale must be positive")
    encoded_color = bytes(color)
    for character_index, character in enumerate(text.upper()):
        glyph = _FONT.get(character, _FONT["?"])
        origin_x = x + character_index * 6 * scale
        for glyph_y, pattern in enumerate(glyph):
            for glyph_x, enabled in enumerate(pattern):
                if enabled != "1":
                    continue
                for dy in range(scale):
                    target_y = y + glyph_y * scale + dy
                    if not 0 <= target_y < height:
                        continue
                    for dx in range(scale):
                        target_x = origin_x + glyph_x * scale + dx
                        if 0 <= target_x < width:
                            offset = (target_y * width + target_x) * 3
                            rgb[offset:offset + 3] = encoded_color


class ScaleTextRenderer(Protocol):
    backend: str
    line_height: int

    def width(self, text: str) -> int: ...

    def render(
        self,
        rgb: bytes | bytearray,
        width: int,
        height: int,
        labels: list[tuple[int, int, str, tuple[int, int, int]]],
    ) -> bytes: ...


class BitmapScaleTextRenderer:
    backend = "bitmap"

    def __init__(self, *, scale: int) -> None:
        self.scale = scale
        self.line_height = 7 * scale

    def width(self, text: str) -> int:
        return bitmap_text_width(text, scale=self.scale)

    def render(self, rgb, width, height, labels) -> bytes:
        canvas = bytearray(rgb)
        for x, y, text, color in labels:
            draw_bitmap_text(canvas, width, height, x, y, text, color, scale=self.scale)
        return bytes(canvas)


class PillowScaleTextRenderer:
    """C-backed FreeType text renderer used by the integrated graphical scale."""

    backend = "pillow"

    def __init__(self, *, font_size: int, font_name: str = "DejaVuSansMono.ttf") -> None:
        from PIL import ImageFont

        if font_size <= 0:
            raise ValueError("FreeType font size must be positive")
        self.font = ImageFont.truetype(font_name, font_size)
        self.line_height = font_size

    def width(self, text: str) -> int:
        return max(1, math.ceil(self.font.getlength(text)))

    def render(self, rgb, width, height, labels) -> bytes:
        from PIL import Image, ImageDraw

        image = Image.frombytes("RGB", (width, height), bytes(rgb))
        draw = ImageDraw.Draw(image)
        for x, y, text, color in labels:
            draw.text((x, y), text, fill=color, font=self.font, anchor="lt")
        return image.tobytes()


def scale_text_renderer(
    backend: str,
    *,
    font_scale: int,
    font_name: str = "DejaVuSansMono.ttf",
) -> ScaleTextRenderer:
    """Resolve FreeType text with a deterministic bitmap fallback."""
    normalized = backend.lower()
    if normalized not in ("auto", "pillow", "bitmap"):
        raise ValueError("scale font backend must be auto, pillow or bitmap")
    if normalized in ("auto", "pillow"):
        try:
            return PillowScaleTextRenderer(font_size=8 * font_scale, font_name=font_name)
        except (ImportError, OSError):
            if normalized == "pillow":
                raise RuntimeError("Pillow/FreeType scale font is unavailable")
    return BitmapScaleTextRenderer(scale=font_scale)


@dataclass(frozen=True)
class GraphicalScaleResult:
    image: RasterImage
    frequency_labels: tuple[str, ...]
    preset_labels: tuple[str, ...]
    tuning_top: int
    tick_top: int
    preset_stem_top: int
    text_backend: str


def _frequency_column(frequency_khz: float, start_khz: float, end_khz: float, width: int) -> int | None:
    if not start_khz <= frequency_khz <= end_khz:
        return None
    return round((frequency_khz - start_khz) / (end_khz - start_khz) * (width - 1))


def _set_pixel(rgb: bytearray, width: int, x: int, y: int, color: tuple[int, int, int]) -> None:
    if 0 <= x < width and 0 <= y < len(rgb) // (width * 3):
        offset = (y * width + x) * 3
        rgb[offset:offset + 3] = bytes(color)


def compose_waterfall_scale(
    waterfall: RasterImage,
    start_khz: float,
    end_khz: float,
    *,
    tuned_khz: float,
    selected_khz: float,
    low_cut_hz: int,
    high_cut_hz: int,
    presets: Mapping[str, Mapping[str, Any]],
    label_target_pixels: int = 150,
    font_scale: int = 2,
    font_backend: str = "auto",
    font_name: str = "DejaVuSansMono.ttf",
) -> GraphicalScaleResult:
    """Compose pixel-aligned tuning, frequency and preset scales below W/F."""
    if end_khz <= start_khz or label_target_pixels < 20 or font_scale <= 0:
        raise ValueError("invalid graphical scale dimensions")
    text_renderer = scale_text_renderer(font_backend, font_scale=font_scale, font_name=font_name)
    tuning_height = 8
    tick_height = 5
    label_height = text_renderer.line_height + 3
    preset_stem_height = 5
    preset_label_height = text_renderer.line_height + 2
    footer_height = tuning_height + tick_height + label_height + preset_stem_height + preset_label_height
    output_height = waterfall.height + footer_height
    rgb = bytearray(waterfall.rgb + b"\x00" * waterfall.width * footer_height * 3)
    tuning_top = waterfall.height

    low = _frequency_column(tuned_khz + low_cut_hz / 1000.0, start_khz, end_khz, waterfall.width)
    center = _frequency_column(tuned_khz, start_khz, end_khz, waterfall.width)
    high = _frequency_column(tuned_khz + high_cut_hz / 1000.0, start_khz, end_khz, waterfall.width)
    if low is not None and high is not None:
        low, high = sorted((low, high))
        for x in range(low, high + 1):
            for y in (tuning_top + 2, tuning_top + 3):
                _set_pixel(rgb, waterfall.width, x, y, PASSBAND_SCALE_RGB)
        for x in range(low, min(waterfall.width, low + 2)):
            for y in range(tuning_top, tuning_top + 4):
                _set_pixel(rgb, waterfall.width, x, y, PASSBAND_SCALE_RGB)
        for x in range(max(0, high - 1), high + 1):
            for y in range(tuning_top, tuning_top + 4):
                _set_pixel(rgb, waterfall.width, x, y, PASSBAND_SCALE_RGB)
    if center is not None:
        for x in range(center, min(waterfall.width, center + 2)):
            for y in range(tuning_top + 2, tuning_top + 7):
                _set_pixel(rgb, waterfall.width, x, y, PASSBAND_SCALE_RGB)
    selected = _frequency_column(selected_khz, start_khz, end_khz, waterfall.width)
    if selected is not None and selected != center:
        for radius in range(3):
            y = tuning_top + tuning_height - 1 - radius
            for x in range(max(0, selected - radius), min(waterfall.width, selected + radius + 1)):
                _set_pixel(rgb, waterfall.width, x, y, CURSOR_MARKER_RGB)

    tick_top = tuning_top + tuning_height
    target_labels = max(2, waterfall.width // label_target_pixels)
    step = choose_frequency_tick_step((end_khz - start_khz) / (target_labels - 1))
    decimals = frequency_label_decimals(step)
    frequency_labels: list[str] = []
    text_labels: list[tuple[int, int, str, tuple[int, int, int]]] = []
    occupied: list[tuple[int, int]] = []
    frequency = math.ceil((start_khz - step * 1e-12) / step) * step
    while frequency <= end_khz + step * 1e-9:
        column = _frequency_column(frequency, start_khz, end_khz, waterfall.width)
        if column is not None:
            for y in range(tick_top, tick_top + tick_height):
                _set_pixel(rgb, waterfall.width, column, y, FREQUENCY_SCALE_RGB)
            label = f"{frequency:.{decimals}f}"
            label_width = text_renderer.width(label)
            label_x = min(max(0, column - label_width // 2), max(0, waterfall.width - label_width))
            interval = (label_x, label_x + label_width)
            if not any(interval[0] < used[1] + font_scale and interval[1] + font_scale > used[0] for used in occupied):
                text_labels.append((
                    label_x,
                    tick_top + tick_height + 1,
                    label,
                    FREQUENCY_SCALE_RGB,
                ))
                occupied.append(interval)
                frequency_labels.append(label)
        frequency += step

    preset_stem_top = tick_top + tick_height + label_height
    preset_labels: list[str] = []
    preset_occupied: list[tuple[int, int]] = []
    visible: list[tuple[float, str]] = []
    for register, preset in presets.items():
        if "frequency_khz" in preset:
            frequency_khz = float(preset["frequency_khz"])
            if start_khz <= frequency_khz <= end_khz:
                visible.append((frequency_khz, f"{register} {frequency_khz:.3f}".upper()))
    for frequency_khz, label in sorted(visible):
        column = _frequency_column(frequency_khz, start_khz, end_khz, waterfall.width)
        assert column is not None
        for y in range(preset_stem_top, preset_stem_top + preset_stem_height):
            _set_pixel(rgb, waterfall.width, column, y, PRESET_SCALE_RGB)
        label_width = text_renderer.width(label)
        label_x = min(max(0, column - label_width // 2), max(0, waterfall.width - label_width))
        interval = (label_x, label_x + label_width)
        if any(interval[0] < used[1] + font_scale and interval[1] + font_scale > used[0] for used in preset_occupied):
            continue
        text_labels.append((
            label_x,
            preset_stem_top + preset_stem_height + 1,
            label,
            PRESET_SCALE_RGB,
        ))
        preset_occupied.append(interval)
        preset_labels.append(label)

    rendered_rgb = text_renderer.render(rgb, waterfall.width, output_height, text_labels)
    return GraphicalScaleResult(
        image=RasterImage(waterfall.width, output_height, rendered_rgb),
        frequency_labels=tuple(frequency_labels),
        preset_labels=tuple(preset_labels),
        tuning_top=tuning_top,
        tick_top=tick_top,
        preset_stem_top=preset_stem_top,
        text_backend=text_renderer.backend,
    )
