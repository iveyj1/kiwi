"""Curses waterfall pane: half-block cells drawn into a curses window.

Everything here takes its curses primitives as arguments rather than importing
curses at module scope, so the drawing logic is testable with a fake window and
no terminal. `kiwi_client.tui` supplies the real `curses` callables.

Reduction from 1024 bins to pane width happens at draw time, not on the way into
the buffer, so the buffer keeps full resolution and the pane can be resized.
"""

from __future__ import annotations

from typing import Callable, Sequence

from kiwi_client.waterfall_display import (
    DEFAULT_LEVELS,
    DEFAULT_MAX_DBM,
    DEFAULT_MIN_DBM,
    HALF_BLOCK,
    HalfBlockCell,
    WaterfallImageBuffer,
    dbm_to_level,
    half_block_cells,
)
from kiwi_client.waterfall_palette import DEFAULT_COLORMAP, pair_number, palette_color, required_pairs
from kiwi_client.waterfall_render import DEFAULT_REDUCTION, reduce_bins


def pane_cells(
    buffer: WaterfallImageBuffer,
    *,
    width: int,
    height: int,
    min_dbm: float = DEFAULT_MIN_DBM,
    max_dbm: float = DEFAULT_MAX_DBM,
    levels: int = DEFAULT_LEVELS,
    reduction: str = DEFAULT_REDUCTION,
) -> tuple[tuple[HalfBlockCell, ...], ...]:
    """Render buffer contents as half-block cells sized for the pane.

    Each character row shows two waterfall rows, so a pane `height` characters
    tall displays `2 * height` frames.
    """
    if width < 1 or height < 0:
        raise ValueError("pane width must be >= 1 and height >= 0")
    if height == 0:
        return ()
    rows = buffer.rows(2 * height)
    if not rows:
        return ()
    level_rows = [
        tuple(
            dbm_to_level(value, min_dbm=min_dbm, max_dbm=max_dbm, levels=levels)
            for value in reduce_bins(row, width, reduction=reduction)
        )
        for row in rows
    ]
    return half_block_cells(level_rows, height=height)


def init_waterfall_pairs(
    init_pair: Callable[[int, int, int], None],
    *,
    levels: int = DEFAULT_LEVELS,
    max_pairs: int | None = None,
    colormap: str = DEFAULT_COLORMAP,
) -> int:
    """Register one curses colour pair per (upper, lower) level combination.

    Returns the number of pairs registered. Raises if the terminal cannot
    provide enough, rather than silently drawing a wrong-coloured waterfall.
    """
    needed = required_pairs(levels)
    if max_pairs is not None and needed > max_pairs:
        raise RuntimeError(
            f"waterfall pane needs {needed} colour pairs for {levels} levels but the "
            f"terminal offers {max_pairs}; reduce levels"
        )
    colors = [palette_color(level, levels=levels, colormap=colormap) for level in range(levels)]
    for upper in range(levels):
        for lower in range(levels):
            init_pair(pair_number(upper, lower, levels=levels), colors[upper], colors[lower])
    return levels * levels


def draw_waterfall_pane(
    window,
    cells: Sequence[Sequence[HalfBlockCell]],
    *,
    top: int,
    left: int = 0,
    color_pair: Callable[[int], int],
    levels: int = DEFAULT_LEVELS,
) -> int:
    """Draw half-block cells into a curses-like window; return rows drawn.

    `window` needs only `addstr(y, x, text, attr)`. `color_pair` maps a pair
    number to a curses attribute.
    """
    drawn = 0
    for offset, row in enumerate(cells):
        column = 0
        while column < len(row):
            cell = row[column]
            run = column
            while run < len(row) and row[run].upper == cell.upper and row[run].lower == cell.lower:
                run += 1
            attribute = color_pair(pair_number(cell.upper, cell.lower, levels=levels))
            try:
                window.addstr(top + offset, left + column, HALF_BLOCK * (run - column), attribute)
            except Exception:
                # curses raises when writing the last cell of the window; the
                # rest of the pane is still valid, so stop this row and continue.
                break
            column = run
        drawn += 1
    return drawn
