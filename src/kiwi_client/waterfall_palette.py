"""Palette mapping for the curses waterfall pane.

Levels from `waterfall_display` are mapped to xterm-256 palette indices. The
ramp is chosen from the standard 6x6x6 colour cube rather than redefined with
`init_color()`, so it works on terminals that refuse to change their palette.

A half-block cell needs a (foreground, background) pair, so a palette of N
levels needs up to N*N curses colour pairs. With N=24 that is 576, far below the
32767 pairs the local terminals report.
"""

from __future__ import annotations

# Classic waterfall ramp, dark to hot, as (r, g, b) in the xterm 6x6x6 cube.
_RAMP_RGB = (
    (0, 0, 0), (0, 0, 1), (0, 0, 2), (0, 0, 3),
    (0, 1, 3), (0, 1, 4), (0, 2, 4), (0, 3, 5),
    (0, 4, 5), (1, 5, 5), (1, 5, 4), (2, 5, 3),
    (3, 5, 2), (4, 5, 1), (5, 5, 0), (5, 4, 0),
    (5, 3, 0), (5, 2, 0), (5, 1, 0), (5, 0, 0),
    (5, 1, 1), (5, 2, 2), (5, 3, 3), (5, 5, 5),
)

PALETTE_LEVELS = len(_RAMP_RGB)


def cube_index(red: int, green: int, blue: int) -> int:
    """Return the xterm-256 index for one 6x6x6 colour-cube entry."""
    for name, value in (("red", red), ("green", green), ("blue", blue)):
        if not 0 <= value <= 5:
            raise ValueError(f"{name} must be in range 0..5, got {value}")
    return 16 + 36 * red + 6 * green + blue


def palette_color(level: int, *, levels: int = PALETTE_LEVELS) -> int:
    """Return the xterm-256 colour index for one display level."""
    if levels < 2:
        raise ValueError("palette needs at least two levels")
    if not 0 <= level < levels:
        raise ValueError(f"level {level} outside 0..{levels - 1}")
    # Resample the fixed ramp if the caller uses a different level count.
    index = level if levels == PALETTE_LEVELS else level * (PALETTE_LEVELS - 1) // (levels - 1)
    return cube_index(*_RAMP_RGB[index])


def palette_indices(levels: int = PALETTE_LEVELS) -> tuple[int, ...]:
    """Return the xterm-256 colour index for every level, dark to hot."""
    return tuple(palette_color(level, levels=levels) for level in range(levels))


def pair_number(upper: int, lower: int, *, levels: int = PALETTE_LEVELS, base: int = 1) -> int:
    """Return a stable curses pair number for one (upper, lower) level pair.

    Pair 0 is reserved by curses, so numbering starts at `base`.
    """
    if not 0 <= upper < levels or not 0 <= lower < levels:
        raise ValueError(f"levels must be in range 0..{levels - 1}")
    return base + upper * levels + lower


def required_pairs(levels: int = PALETTE_LEVELS, *, base: int = 1) -> int:
    """Return how many curses colour pairs a palette of this size needs."""
    return base + levels * levels
