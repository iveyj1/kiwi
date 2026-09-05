"""Pixel-aligned graphical scales composed beneath waterfall history."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Mapping

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


@dataclass(frozen=True)
class GraphicalScaleResult:
    image: RasterImage
    frequency_labels: tuple[str, ...]
    preset_labels: tuple[str, ...]
    tuning_top: int
    tick_top: int
    preset_stem_top: int


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
) -> GraphicalScaleResult:
    """Compose pixel-aligned tuning, frequency and preset scales below W/F."""
    if end_khz <= start_khz or label_target_pixels < 20 or font_scale <= 0:
        raise ValueError("invalid graphical scale dimensions")
    tuning_height = 8
    tick_height = 5
    label_height = 7 * font_scale + 3
    preset_stem_height = 5
    preset_label_height = 7 * font_scale + 2
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
    occupied: list[tuple[int, int]] = []
    frequency = math.ceil((start_khz - step * 1e-12) / step) * step
    while frequency <= end_khz + step * 1e-9:
        column = _frequency_column(frequency, start_khz, end_khz, waterfall.width)
        if column is not None:
            for y in range(tick_top, tick_top + tick_height):
                _set_pixel(rgb, waterfall.width, column, y, FREQUENCY_SCALE_RGB)
            label = f"{frequency:.{decimals}f}"
            label_width = bitmap_text_width(label, scale=font_scale)
            label_x = min(max(0, column - label_width // 2), max(0, waterfall.width - label_width))
            interval = (label_x, label_x + label_width)
            if not any(interval[0] < used[1] + font_scale and interval[1] + font_scale > used[0] for used in occupied):
                draw_bitmap_text(
                    rgb,
                    waterfall.width,
                    output_height,
                    label_x,
                    tick_top + tick_height + 1,
                    label,
                    FREQUENCY_SCALE_RGB,
                    scale=font_scale,
                )
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
        label_width = bitmap_text_width(label, scale=font_scale)
        label_x = min(max(0, column - label_width // 2), max(0, waterfall.width - label_width))
        interval = (label_x, label_x + label_width)
        if any(interval[0] < used[1] + font_scale and interval[1] + font_scale > used[0] for used in preset_occupied):
            continue
        draw_bitmap_text(
            rgb,
            waterfall.width,
            output_height,
            label_x,
            preset_stem_top + preset_stem_height + 1,
            label,
            PRESET_SCALE_RGB,
            scale=font_scale,
        )
        preset_occupied.append(interval)
        preset_labels.append(label)

    return GraphicalScaleResult(
        image=RasterImage(waterfall.width, output_height, bytes(rgb)),
        frequency_labels=tuple(frequency_labels),
        preset_labels=tuple(preset_labels),
        tuning_top=tuning_top,
        tick_top=tick_top,
        preset_stem_top=preset_stem_top,
    )
