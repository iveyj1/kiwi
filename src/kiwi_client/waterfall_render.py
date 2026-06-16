"""Deterministic waterfall render helpers."""

from __future__ import annotations

from kiwi_client.waterfall import WaterfallFrame

DEFAULT_ASCII_RAMP = " .:-=+*#%@"


def dbm_to_ramp_index(
    dbm: int | float,
    *,
    min_dbm: int | float = -110,
    max_dbm: int | float = 0,
    ramp: str = DEFAULT_ASCII_RAMP,
) -> int:
    """Map one dBm value onto a fixed ramp index with clamping."""
    if len(ramp) < 2:
        raise ValueError("waterfall ramp must contain at least two characters")
    if max_dbm <= min_dbm:
        raise ValueError("max_dbm must be greater than min_dbm")
    clamped = min(max(dbm, min_dbm), max_dbm)
    fraction = (clamped - min_dbm) / (max_dbm - min_dbm)
    return int(fraction * (len(ramp) - 1) + 0.5)


def render_ascii_waterfall_row(
    frame: WaterfallFrame,
    *,
    min_dbm: int | float = -110,
    max_dbm: int | float = 0,
    ramp: str = DEFAULT_ASCII_RAMP,
) -> str:
    """Render one waterfall frame as a deterministic ASCII intensity row."""
    return "".join(ramp[dbm_to_ramp_index(value, min_dbm=min_dbm, max_dbm=max_dbm, ramp=ramp)] for value in frame.dbm)
