"""Renderer-neutral waterfall history and raster image helpers."""

from __future__ import annotations

import struct
import zlib
from collections import deque
from dataclasses import dataclass
from typing import Sequence

from kiwi_client.waterfall import WaterfallFrame

# Compact, deterministic waterfall palette: black -> blue -> cyan -> yellow -> white.
TUNED_MARKER_RGB = (255, 255, 255)
PASSBAND_MARKER_RGB = (255, 96, 0)
CURSOR_MARKER_RGB = (255, 0, 255)

_PALETTE = (
    (0.00, (0, 0, 0)),
    (0.25, (0, 0, 128)),
    (0.50, (0, 255, 255)),
    (0.75, (255, 255, 0)),
    (1.00, (255, 255, 255)),
)


@dataclass(frozen=True)
class WaterfallOverlay:
    """Frequency markers to draw over a mapped waterfall raster."""

    start_khz: float
    end_khz: float
    tuned_khz: float | None = None
    low_cut_hz: int | None = None
    high_cut_hz: int | None = None
    show_tuned_marker: bool = True
    cursor_khz: float | None = None

    def __post_init__(self) -> None:
        if self.end_khz <= self.start_khz:
            raise ValueError("overlay end_khz must be greater than start_khz")
        if (
            self.low_cut_hz is not None
            and self.high_cut_hz is not None
            and self.high_cut_hz <= self.low_cut_hz
        ):
            raise ValueError("overlay high_cut_hz must be greater than low_cut_hz")


@dataclass(frozen=True)
class RasterImage:
    """Packed 24-bit RGB raster image."""

    width: int
    height: int
    rgb: bytes

    def __post_init__(self) -> None:
        if self.width <= 0 or self.height <= 0:
            raise ValueError("raster width and height must be positive")
        if len(self.rgb) != self.width * self.height * 3:
            raise ValueError("RGB byte count does not match raster dimensions")


class WaterfallHistory:
    """Fixed-height history of numeric W/F rows, independent from render backends."""

    def __init__(self, *, max_rows: int, width: int | None = None) -> None:
        if max_rows <= 0:
            raise ValueError("waterfall history max_rows must be positive")
        if width is not None and width <= 0:
            raise ValueError("waterfall history width must be positive")
        self.max_rows = max_rows
        self.width = width
        self._rows: deque[tuple[int | float, ...]] = deque(maxlen=max_rows)

    def append(self, frame: WaterfallFrame) -> None:
        """Append one decoded frame, establishing or validating bin width."""
        row = tuple(frame.dbm)
        if not row:
            raise ValueError("waterfall frame contains no dBm bins")
        if self.width is None:
            self.width = len(row)
        if len(row) != self.width:
            raise ValueError(f"waterfall frame width {len(row)} does not match history width {self.width}")
        self._rows.append(row)

    def rows(
        self,
        *,
        newest_at_top: bool = False,
        pad_dbm: int | float | None = None,
    ) -> tuple[tuple[int | float, ...], ...]:
        """Return display rows, optionally padding absent old history rows."""
        rows = tuple(self._rows)
        if newest_at_top:
            rows = tuple(reversed(rows))
        if pad_dbm is not None and self.width is not None and len(rows) < self.max_rows:
            padding = tuple(pad_dbm for _ in range(self.width))
            missing = tuple(padding for _ in range(self.max_rows - len(rows)))
            # Keep the newest edge anchored: bottom convention pads above, top convention below.
            rows = rows + missing if newest_at_top else missing + rows
        return rows

    def __len__(self) -> int:
        return len(self._rows)


def dbm_to_rgb(
    dbm: int | float,
    *,
    min_dbm: int | float,
    max_dbm: int | float,
) -> tuple[int, int, int]:
    """Map one fixed-scale dBm value to a deterministic RGB palette."""
    if max_dbm <= min_dbm:
        raise ValueError("max_dbm must be greater than min_dbm")
    clamped = min(max(dbm, min_dbm), max_dbm)
    fraction = (clamped - min_dbm) / (max_dbm - min_dbm)
    for index in range(1, len(_PALETTE)):
        upper_position, upper_rgb = _PALETTE[index]
        lower_position, lower_rgb = _PALETTE[index - 1]
        if fraction <= upper_position:
            local = (fraction - lower_position) / (upper_position - lower_position)
            return tuple(int(low + (high - low) * local + 0.5) for low, high in zip(lower_rgb, upper_rgb))
    return _PALETTE[-1][1]


def render_dbm_rows(
    rows: Sequence[Sequence[int | float]],
    *,
    min_dbm: int | float,
    max_dbm: int | float,
) -> RasterImage:
    """Render a non-empty rectangular dBm matrix to packed RGB pixels."""
    if max_dbm <= min_dbm:
        raise ValueError("max_dbm must be greater than min_dbm")
    if not rows or not rows[0]:
        raise ValueError("waterfall raster requires at least one non-empty row")
    width = len(rows[0])
    if any(len(row) != width for row in rows):
        raise ValueError("waterfall rows must be rectangular")
    # Current uncompressed W/F frames contain integer dBm values in -255..0.
    # A per-render lookup avoids repeating palette interpolation for every history pixel.
    integer_lookup = tuple(dbm_to_rgb(value, min_dbm=min_dbm, max_dbm=max_dbm) for value in range(-255, 1))
    rgb = bytearray()
    for row in rows:
        for value in row:
            if isinstance(value, int) and -255 <= value <= 0:
                rgb.extend(integer_lookup[value + 255])
            else:
                rgb.extend(dbm_to_rgb(value, min_dbm=min_dbm, max_dbm=max_dbm))
    return RasterImage(width=width, height=len(rows), rgb=bytes(rgb))


def _frequency_column(frequency_khz: float, overlay: WaterfallOverlay, width: int) -> int | None:
    if frequency_khz < overlay.start_khz or frequency_khz > overlay.end_khz:
        return None
    fraction = (frequency_khz - overlay.start_khz) / (overlay.end_khz - overlay.start_khz)
    return round(fraction * (width - 1))


def apply_frequency_overlay(image: RasterImage, overlay: WaterfallOverlay) -> RasterImage:
    """Draw tuned-frequency and passband-edge columns onto a copy of an image."""
    markers: list[tuple[int, tuple[int, int, int]]] = []
    if overlay.tuned_khz is not None:
        if overlay.low_cut_hz is not None:
            column = _frequency_column(
                overlay.tuned_khz + overlay.low_cut_hz / 1000.0,
                overlay,
                image.width,
            )
            if column is not None:
                markers.append((column, PASSBAND_MARKER_RGB))
        if overlay.high_cut_hz is not None:
            column = _frequency_column(
                overlay.tuned_khz + overlay.high_cut_hz / 1000.0,
                overlay,
                image.width,
            )
            if column is not None:
                markers.append((column, PASSBAND_MARKER_RGB))
        if overlay.show_tuned_marker:
            column = _frequency_column(overlay.tuned_khz, overlay, image.width)
            if column is not None:
                markers.append((column, TUNED_MARKER_RGB))
    if overlay.cursor_khz is not None:
        column = _frequency_column(overlay.cursor_khz, overlay, image.width)
        if column is not None:
            markers.append((column, CURSOR_MARKER_RGB))
    if not markers:
        return image

    rgb = bytearray(image.rgb)
    for row in range(image.height):
        for column, color in markers:
            offset = (row * image.width + column) * 3
            rgb[offset:offset + 3] = bytes(color)
    return RasterImage(width=image.width, height=image.height, rgb=bytes(rgb))


def _png_chunk(kind: bytes, data: bytes) -> bytes:
    return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF)


def encode_png(image: RasterImage) -> bytes:
    """Encode a packed RGB image as a dependency-free PNG."""
    header = struct.pack(">IIBBBBB", image.width, image.height, 8, 2, 0, 0, 0)
    stride = image.width * 3
    scanlines = b"".join(b"\x00" + image.rgb[offset:offset + stride] for offset in range(0, len(image.rgb), stride))
    return b"\x89PNG\r\n\x1a\n" + _png_chunk(b"IHDR", header) + _png_chunk(b"IDAT", zlib.compress(scanlines)) + _png_chunk(b"IEND", b"")
