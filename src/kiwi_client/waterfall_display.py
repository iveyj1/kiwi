"""Waterfall display model shared by every renderer.

This is the layer between decoded W/F frames and any particular output: the
curses half-block pane, the offline PNG tool, and any future terminal graphics
backend. It holds recent rows, applies calibration and scaling, and quantises
to palette levels. It knows nothing about curses, terminals, or files.

Colour depth note: the curses pane is limited to the terminal's 256-colour
palette, because ncurses here has no extended-pair support. Raw terminal output
could do 24-bit, but a curses pane cannot, so the model quantises to a modest
number of levels and lets each backend map levels to its own colours. See
`waterfall_palette` for the KiwiSDR colour ramps themselves.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from typing import Iterable, Sequence

DEFAULT_LEVELS = 32  # must match waterfall_palette.PALETTE_LEVELS
DEFAULT_MIN_DBM = -110.0
DEFAULT_MAX_DBM = -20.0

# Upper half block. Drawn with foreground = upper row, background = lower row,
# so one character cell shows two waterfall rows.
HALF_BLOCK = "▀"


def dbm_to_level(
    dbm: float,
    *,
    min_dbm: float = DEFAULT_MIN_DBM,
    max_dbm: float = DEFAULT_MAX_DBM,
    levels: int = DEFAULT_LEVELS,
) -> int:
    """Quantise one dBm value to a palette level in `0..levels-1`, clamping."""
    if levels < 2:
        raise ValueError("waterfall display needs at least two levels")
    if max_dbm <= min_dbm:
        raise ValueError("max_dbm must be greater than min_dbm")
    clamped = min(max(dbm, min_dbm), max_dbm)
    fraction = (clamped - min_dbm) / (max_dbm - min_dbm)
    return min(levels - 1, int(fraction * levels))


@dataclass(frozen=True)
class HalfBlockCell:
    """One character cell showing two stacked waterfall rows."""

    upper: int
    lower: int


class WaterfallImageBuffer:
    """Fixed-width ring of recent waterfall rows, newest first.

    Rows are stored as calibrated dBm, not as palette levels or pixels, so the
    display scale can be changed without recapturing. Width is fixed by the
    first row appended unless given explicitly; later rows must match, because
    silently resampling would misreport where a signal sits.
    """

    def __init__(self, *, max_rows: int = 64, width: int | None = None) -> None:
        if max_rows < 1:
            raise ValueError("waterfall buffer needs room for at least one row")
        if width is not None and width < 1:
            raise ValueError("waterfall buffer width must be >= 1")
        self._rows: deque[tuple[float, ...]] = deque(maxlen=max_rows)
        self._width = width

    @property
    def width(self) -> int | None:
        """Return the fixed row width, or None before the first row arrives."""
        return self._width

    @property
    def max_rows(self) -> int:
        return self._rows.maxlen or 0

    def __len__(self) -> int:
        return len(self._rows)

    def clear(self) -> None:
        """Drop all rows, keeping the configured width."""
        self._rows.clear()

    def append(self, dbm_row: Sequence[float], *, calibration_db: float = 0.0) -> None:
        """Add one row of dBm values, newest-first, applying a calibration offset."""
        if not dbm_row:
            raise ValueError("cannot append an empty waterfall row")
        if self._width is None:
            self._width = len(dbm_row)
        elif len(dbm_row) != self._width:
            raise ValueError(
                f"waterfall row width {len(dbm_row)} does not match buffer width {self._width}"
            )
        self._rows.appendleft(tuple(value + calibration_db for value in dbm_row))

    def rows(self, count: int | None = None) -> tuple[tuple[float, ...], ...]:
        """Return recent rows newest-first, at most `count` of them."""
        if count is None:
            return tuple(self._rows)
        if count < 0:
            raise ValueError("row count must be >= 0")
        return tuple(self._rows)[:count]

    def levels(
        self,
        count: int | None = None,
        *,
        min_dbm: float = DEFAULT_MIN_DBM,
        max_dbm: float = DEFAULT_MAX_DBM,
        levels: int = DEFAULT_LEVELS,
    ) -> tuple[tuple[int, ...], ...]:
        """Return recent rows newest-first as quantised palette levels."""
        return tuple(
            tuple(dbm_to_level(value, min_dbm=min_dbm, max_dbm=max_dbm, levels=levels) for value in row)
            for row in self.rows(count)
        )


def half_block_cells(
    level_rows: Sequence[Sequence[int]],
    *,
    height: int | None = None,
    fill: int = 0,
) -> tuple[tuple[HalfBlockCell, ...], ...]:
    """Pair consecutive level rows into character cells, two data rows per cell.

    `height` is the number of character rows wanted. Missing data is padded with
    `fill` so a partly filled buffer still renders a rectangle rather than a
    ragged edge.
    """
    if height is not None and height < 0:
        raise ValueError("height must be >= 0")
    rows = list(level_rows)
    if not rows:
        if not height:
            return ()
        raise ValueError("cannot infer cell width with no rows and a non-zero height")
    width = len(rows[0])
    if any(len(row) != width for row in rows):
        raise ValueError("level rows are not rectangular")

    cell_rows = height if height is not None else (len(rows) + 1) // 2
    blank = [fill] * width
    output = []
    for index in range(cell_rows):
        upper = rows[2 * index] if 2 * index < len(rows) else blank
        lower = rows[2 * index + 1] if 2 * index + 1 < len(rows) else blank
        output.append(tuple(HalfBlockCell(upper=u, lower=l) for u, l in zip(upper, lower)))
    return tuple(output)


def buffer_from_frames(
    dbm_rows: Iterable[Sequence[float]],
    *,
    max_rows: int = 64,
    calibration_db: float = 0.0,
) -> WaterfallImageBuffer:
    """Build a buffer from dBm rows given oldest-first, as fixtures store them."""
    buffer = WaterfallImageBuffer(max_rows=max_rows)
    for row in dbm_rows:
        buffer.append(row, calibration_db=calibration_db)
    return buffer


def auto_scale_dbm(
    rows,
    *,
    floor_percentile: float = 0.20,
    peak_percentile: float = 0.999,
    headroom_db: float = 4.0,
    min_range_db: float = 25.0,
) -> tuple[float, float] | None:
    """Return a (min_dbm, max_dbm) display window fitted to recent rows.

    A fixed window cannot serve every zoom: the noise floor moves by roughly
    3 dB per zoom step as the bins narrow. Anchoring the low end just under the
    measured floor keeps it at the dark end of the palette, which is what makes
    signals stand out instead of the whole image sitting mid-ramp.

    Returns None when there is nothing to measure.
    """
    values = sorted(value for row in rows for value in row)
    if not values:
        return None
    floor = values[min(len(values) - 1, int(len(values) * floor_percentile))]
    peak = values[min(len(values) - 1, int(len(values) * peak_percentile))]
    low = floor - headroom_db
    high = max(peak + headroom_db, low + min_range_db)
    return (low, high)
