"""Waterfall render helpers.

Everything here is deterministic except `terminal_columns()`, which is the one
function that inspects the environment. CLI layers resolve terminal width once
and pass an explicit column count inward, so render and capture behavior stays
reproducible under test.
"""

from __future__ import annotations

import shutil
from typing import Sequence

from kiwi_client.waterfall import WaterfallFrame

DEFAULT_ASCII_RAMP = " .:-=+*#%@"
DEFAULT_REDUCTION = "max"
REDUCTIONS = ("max", "mean")
FALLBACK_TERMINAL_COLUMNS = 80


def terminal_columns(fallback: int = FALLBACK_TERMINAL_COLUMNS) -> int:
    """Return usable terminal width, falling back when stdout is not a terminal.

    Honours `COLUMNS` before querying the tty, matching normal shell behavior.
    """
    return shutil.get_terminal_size(fallback=(fallback, 24)).columns


def resolve_columns(requested: int | None) -> int | None:
    """Map a `--columns` CLI argument onto a render column count.

    Omitted (`None`) means terminal width; `0` means no reduction at all.
    """
    if requested is None:
        return terminal_columns()
    return None if requested == 0 else requested


def reduce_bins(
    values: Sequence[int | float],
    columns: int | None,
    *,
    reduction: str = DEFAULT_REDUCTION,
) -> tuple[int | float, ...]:
    """Aggregate a bin vector down to `columns` contiguous buckets.

    Bucket edges use `i * len(values) // columns`, so every bin lands in exactly
    one bucket and bucket sizes differ by at most one bin. `columns` of `None`,
    or any count at least as large as the input, returns the input unchanged;
    this never upsamples.

    `max` is the default because a narrow carrier occupying one bin survives
    decimation, while `mean` would bury it in the surrounding noise floor.
    """
    if reduction not in REDUCTIONS:
        raise ValueError(f"waterfall reduction must be one of {REDUCTIONS}")
    if not values:
        raise ValueError("cannot reduce an empty bin vector")
    if columns is None:
        return tuple(values)
    if columns < 1:
        raise ValueError("waterfall column count must be >= 1")
    if columns >= len(values):
        return tuple(values)

    total = len(values)
    aggregate = max if reduction == "max" else (lambda bucket: sum(bucket) / len(bucket))
    return tuple(aggregate(values[i * total // columns : (i + 1) * total // columns]) for i in range(columns))


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
    columns: int | None = None,
    reduction: str = DEFAULT_REDUCTION,
) -> str:
    """Render one waterfall frame as a deterministic ASCII intensity row.

    With `columns` set, bins are reduced to that many characters first, so one
    frame renders as one terminal row instead of wrapping across several.
    """
    values = reduce_bins(frame.dbm, columns, reduction=reduction)
    return "".join(ramp[dbm_to_ramp_index(value, min_dbm=min_dbm, max_dbm=max_dbm, ramp=ramp)] for value in values)
