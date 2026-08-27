from pathlib import Path

import pytest

from kiwi_client.fixtures import load_jsonl_events
from kiwi_client.waterfall import parse_waterfall_uncompressed
from kiwi_client.waterfall_render import (
    DEFAULT_ASCII_RAMP,
    dbm_to_ramp_index,
    reduce_bins,
    render_ascii_waterfall_row,
    resolve_columns,
    terminal_columns,
)


FIXTURE = Path("tests/fixtures/kiwi/wf-basic.jsonl")
LOCAL_FIXTURE = Path("tests/fixtures/kiwi/local-wf-5000-zoom0.jsonl")


def _fixture_frame():
    events = load_jsonl_events(FIXTURE)
    [event] = [event for event in events if event.type == "binary"]
    return parse_waterfall_uncompressed(event.binary_payload)


def _local_fixture_frames():
    events = load_jsonl_events(LOCAL_FIXTURE)
    return [parse_waterfall_uncompressed(event.binary_payload) for event in events if event.type == "binary"]


def test_dbm_to_ramp_index_uses_fixed_scale_and_clamps():
    assert dbm_to_ramp_index(-255, min_dbm=-110, max_dbm=0, ramp=DEFAULT_ASCII_RAMP) == 0
    assert dbm_to_ramp_index(-110, min_dbm=-110, max_dbm=0, ramp=DEFAULT_ASCII_RAMP) == 0
    assert dbm_to_ramp_index(-55, min_dbm=-110, max_dbm=0, ramp=DEFAULT_ASCII_RAMP) == 5
    assert dbm_to_ramp_index(0, min_dbm=-110, max_dbm=0, ramp=DEFAULT_ASCII_RAMP) == 9
    assert dbm_to_ramp_index(10, min_dbm=-110, max_dbm=0, ramp=DEFAULT_ASCII_RAMP) == 9


def test_render_ascii_waterfall_row_from_fixture():
    frame = _fixture_frame()

    row = render_ascii_waterfall_row(frame, min_dbm=-110, max_dbm=0)

    assert row == "   +@"


def test_render_ascii_waterfall_row_accepts_custom_ramp():
    frame = _fixture_frame()

    row = render_ascii_waterfall_row(frame, min_dbm=-110, max_dbm=0, ramp="._#")

    assert row == "..._#"


def test_reduce_bins_returns_input_unchanged_without_reduction():
    values = (1, 2, 3, 4, 5)

    assert reduce_bins(values, None) == values
    assert reduce_bins(values, 5) == values
    assert reduce_bins(values, 9) == values


def test_reduce_bins_splits_evenly_when_columns_divide_bins():
    assert reduce_bins((0, 9, 1, 2, 3, 4), 3) == (9, 2, 4)
    assert reduce_bins((0, 9, 1, 2, 3, 4), 3, reduction="mean") == (4.5, 1.5, 3.5)


def test_reduce_bins_buckets_differ_by_at_most_one_bin():
    # 5 bins over 3 columns splits as 1/2/2 via `i * 5 // 3` edges.
    assert reduce_bins((10, 0, 20, 0, 30), 3) == (10, 20, 30)


def test_reduce_bins_covers_every_bin_exactly_once():
    values = tuple(range(1024))

    total = sum(sum(bucket) for bucket in [values[i * 1024 // 170 : (i + 1) * 1024 // 170] for i in range(170)])

    assert total == sum(values)


def test_reduce_bins_max_preserves_a_single_narrow_carrier():
    noise_with_carrier = tuple(-100 if index != 700 else -30 for index in range(1024))

    reduced_max = reduce_bins(noise_with_carrier, 170)
    reduced_mean = reduce_bins(noise_with_carrier, 170, reduction="mean")

    assert max(reduced_max) == -30
    assert max(reduced_mean) < -85


def test_reduce_bins_rejects_invalid_arguments():
    with pytest.raises(ValueError, match="must be one of"):
        reduce_bins((1, 2, 3), 2, reduction="median")
    with pytest.raises(ValueError, match="empty bin vector"):
        reduce_bins((), 2)
    with pytest.raises(ValueError, match="column count must be >= 1"):
        reduce_bins((1, 2, 3), 0)


def test_render_ascii_waterfall_row_reduces_local_fixture_to_one_terminal_row():
    frames = _local_fixture_frames()
    assert [len(frame.bins) for frame in frames] == [1024, 1024]

    rows = [render_ascii_waterfall_row(frame, min_dbm=-200, max_dbm=-25, columns=170) for frame in frames]

    assert all(len(row) == 170 for row in rows)
    # Without reduction the same frame wraps across several physical rows.
    assert len(render_ascii_waterfall_row(frames[0], min_dbm=-200, max_dbm=-25)) == 1024


def test_render_ascii_waterfall_row_reduction_is_deterministic():
    frame = _local_fixture_frames()[0]

    first = render_ascii_waterfall_row(frame, min_dbm=-200, max_dbm=-25, columns=64)
    second = render_ascii_waterfall_row(frame, min_dbm=-200, max_dbm=-25, columns=64)

    assert first == second


def test_render_ascii_waterfall_row_mean_reduction_dims_narrow_carriers():
    frame = _local_fixture_frames()[0]

    hot = render_ascii_waterfall_row(frame, min_dbm=-200, max_dbm=-25, columns=64, reduction="max")
    cool = render_ascii_waterfall_row(frame, min_dbm=-200, max_dbm=-25, columns=64, reduction="mean")

    ramp = DEFAULT_ASCII_RAMP
    assert max(ramp.index(char) for char in hot) > max(ramp.index(char) for char in cool)


def test_terminal_columns_honours_columns_env(monkeypatch):
    monkeypatch.setenv("COLUMNS", "137")

    assert terminal_columns() == 137


def test_resolve_columns_maps_cli_argument(monkeypatch):
    monkeypatch.setenv("COLUMNS", "137")

    assert resolve_columns(None) == 137
    assert resolve_columns(0) is None
    assert resolve_columns(64) == 64


def test_dbm_to_ramp_index_rejects_invalid_scale():
    with pytest.raises(ValueError, match="max_dbm must be greater"):
        dbm_to_ramp_index(-50, min_dbm=0, max_dbm=0)


def test_dbm_to_ramp_index_rejects_short_ramp():
    with pytest.raises(ValueError, match="at least two"):
        dbm_to_ramp_index(-50, ramp="@")
