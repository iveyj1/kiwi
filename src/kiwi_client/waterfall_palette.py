"""KiwiSDR waterfall colormaps, and mapping them onto a 256-colour terminal.

The colour ramps here reproduce the KiwiSDR web UI's own waterfall colormaps, so
the terminal pane looks like the browser view of the same receiver. They are
transcribed from `mkcolormap()` in `web/openwebrx/openwebrx.js` of the
Beagle_SDR_GPS firmware source, where `kiwi` is the current default and
`CuteSDR` the older one.

Two stages are kept apart on purpose:

- `colormap_rgb()` returns exact 8-bit RGB, which is what a truecolor or
  graphics-protocol renderer should use.
- `palette_color()` quantises that to the xterm-256 palette, which is all a
  curses pane can address.

A half-block cell needs a (foreground, background) pair, so a palette of N
levels needs up to N*N curses colour pairs. With N=24 that is 576, far below the
32767 pairs the local terminals report.
"""

from __future__ import annotations

DEFAULT_COLORMAP = "kiwi"
COLORMAPS = ("kiwi", "cutesdr", "greyscale")
# Must match waterfall_display.DEFAULT_LEVELS; a test asserts they agree.
#
# Capped by the curses attribute layout, not by the terminal. ncurses packs the
# colour pair number into A_COLOR, which is 0xFF00 here: 8 bits, so only pairs
# 1..255 are addressable through curses.color_pair(). `tput pairs` advertising
# 32767 or 65536 is irrelevant, because reaching those needs init_extended_pair,
# which this Python curses build does not provide.
#
# A half-block cell needs one pair per (upper, lower) combination, so N levels
# need 1 + N*N pairs. N=15 gives 226, inside the limit. N=16 would need 257 and
# every pair above 255 silently wraps to `number & 0xFF`, painting cells with a
# completely unrelated pair.
PALETTE_LEVELS = 15
MAX_ADDRESSABLE_PAIRS = 255

# xterm-256: indices 16..231 are a 6x6x6 cube on these component values,
# and 232..255 are a 24-step grey ramp at 8 + 10*n.
_CUBE_LEVELS = (0, 95, 135, 175, 215, 255)


def _kiwi_rgb(i: int) -> tuple[float, float, float]:
    """Current KiwiSDR default colormap: black, blue, cyan, green, yellow, red."""
    if i < 32:
        return (0.0, 0.0, i * 255 / 31)
    if i < 72:
        return (0.0, (i - 32) * 255 / 39, 255.0)
    if i < 96:
        return (0.0, 255.0, 255 - (i - 72) * 255 / 23)
    if i < 116:
        return ((i - 96) * 255 / 19, 255.0, 0.0)
    if i < 184:
        return (255.0, 255 - (i - 116) * 255 / 67, 0.0)
    return (255.0, 0.0, (i - 184) * 128 / 70)


def _cutesdr_rgb(i: int) -> tuple[float, float, float]:
    """Older KiwiSDR colormap inherited from CuteSDR."""
    if i < 43:
        return (0.0, 0.0, i * 255 / 43)
    if i < 87:
        return (0.0, (i - 43) * 255 / 43, 255.0)
    if i < 120:
        return (0.0, 255.0, 255 - (i - 87) * 255 / 32)
    if i < 154:
        return ((i - 120) * 255 / 33, 255.0, 0.0)
    if i < 217:
        return (255.0, 255 - (i - 154) * 255 / 62, 0.0)
    return (255.0, 0.0, (i - 217) * 128 / 38)


def _greyscale_rgb(i: int) -> tuple[float, float, float]:
    """KiwiSDR greyscale map, which starts above black and can exceed white."""
    value = (255 + 48.0) * i / 255
    return (value, value, value)


_COLORMAPS = {"kiwi": _kiwi_rgb, "cutesdr": _cutesdr_rgb, "greyscale": _greyscale_rgb}


def colormap_rgb(index: int, *, colormap: str = DEFAULT_COLORMAP) -> tuple[int, int, int]:
    """Return exact 8-bit RGB for one 0..255 colormap index.

    Components are rounded then clamped to 0..255, matching `mkcolormap()`,
    which ends with `Math.round()` followed by `w3_clamp(v, 0, 255)`.
    """
    if colormap not in _COLORMAPS:
        raise ValueError(f"unknown colormap {colormap!r}; choose from {COLORMAPS}")
    if not 0 <= index <= 255:
        raise ValueError(f"colormap index {index} outside 0..255")
    return tuple(max(0, min(255, round(value))) for value in _COLORMAPS[colormap](index))


def nearest_xterm256(red: int, green: int, blue: int) -> int:
    """Return the closest xterm-256 palette index to an RGB triple.

    Considers both the 6x6x6 colour cube and the 24-step grey ramp, since greys
    are poorly served by the cube.
    """
    for name, value in (("red", red), ("green", green), ("blue", blue)):
        if not 0 <= value <= 255:
            raise ValueError(f"{name} must be in range 0..255, got {value}")

    def closest_cube(value: int) -> int:
        return min(range(6), key=lambda n: abs(_CUBE_LEVELS[n] - value))

    cube = (closest_cube(red), closest_cube(green), closest_cube(blue))
    cube_rgb = tuple(_CUBE_LEVELS[n] for n in cube)
    cube_index = 16 + 36 * cube[0] + 6 * cube[1] + cube[2]
    cube_error = sum((a - b) ** 2 for a, b in zip(cube_rgb, (red, green, blue)))

    grey_step = min(range(24), key=lambda n: abs((8 + 10 * n) - (red + green + blue) / 3))
    grey_value = 8 + 10 * grey_step
    grey_error = sum((grey_value - c) ** 2 for c in (red, green, blue))

    return cube_index if cube_error <= grey_error else 232 + grey_step


def level_to_colormap_index(level: int, *, levels: int = PALETTE_LEVELS) -> int:
    """Map a display level onto its 0..255 position in the colormap."""
    if levels < 2:
        raise ValueError("palette needs at least two levels")
    if not 0 <= level < levels:
        raise ValueError(f"level {level} outside 0..{levels - 1}")
    return round(level * 255 / (levels - 1))


def palette_color(level: int, *, levels: int = PALETTE_LEVELS, colormap: str = DEFAULT_COLORMAP) -> int:
    """Return the xterm-256 colour index for one display level."""
    index = level_to_colormap_index(level, levels=levels)
    return nearest_xterm256(*colormap_rgb(index, colormap=colormap))


def palette_indices(levels: int = PALETTE_LEVELS, *, colormap: str = DEFAULT_COLORMAP) -> tuple[int, ...]:
    """Return the xterm-256 colour index for every level, dark to hot."""
    return tuple(palette_color(level, levels=levels, colormap=colormap) for level in range(levels))


def palette_rgb(levels: int = PALETTE_LEVELS, *, colormap: str = DEFAULT_COLORMAP) -> tuple[tuple[int, int, int], ...]:
    """Return exact RGB for every level, for renderers that are not palette bound."""
    return tuple(
        colormap_rgb(level_to_colormap_index(level, levels=levels), colormap=colormap)
        for level in range(levels)
    )


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
