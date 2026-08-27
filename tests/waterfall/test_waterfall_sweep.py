"""Pure-analysis tests for the W/F bin offset sweep.

These build synthetic sweeps with a known planted offset and check the analysis
recovers it. No receiver, no network, no fixtures.
"""

import math

import pytest

from kiwi_client.waterfall import WaterfallFrame, WaterfallSpan
from kiwi_client.waterfall_sweep import (
    SweepResult,
    SweepSample,
    analyse_sweep_frames,
    average_dbm,
    find_peak_bin,
    group_frames_by_window,
    noise_floor_dbm,
    sample_window,
)

REFERENCE_HZ = 60_000.0
BINS = 1024


def _span(zoom: int = 9) -> WaterfallSpan:
    return WaterfallSpan(bandwidth_hz=30_000_000.0, zoom=zoom)


def _frame(x_bin_server: int, peak_bin: int, *, peak_dbm: int = -40, floor_dbm: int = -90) -> WaterfallFrame:
    """Build a synthetic frame with a single carrier at `peak_bin`."""
    dbm = [floor_dbm] * BINS
    dbm[peak_bin] = peak_dbm
    return WaterfallFrame(
        sequence=0,
        bins=tuple(255 + value for value in dbm),
        dbm=tuple(dbm),
        x_bin_server=x_bin_server,
    )


def _synthetic_sweep(true_offset: float, *, zoom: int = 9, steps: int = 40, span=None):
    """Return frames for a sweep past REFERENCE_HZ with a planted offset."""
    span = span or _span(zoom)
    base = round((REFERENCE_HZ - span.span_hz / 2) / span.unit_hz)
    frames = []
    for step in range(steps):
        x_bin = base + step
        naive = (REFERENCE_HZ - span.start_hz(x_bin)) / span.bin_width_hz
        peak = round(naive - true_offset)
        frames.append(_frame(x_bin, peak))
    return span, frames


def test_average_dbm_averages_rather_than_max_holds():
    frames = [
        WaterfallFrame(sequence=0, bins=(0, 0), dbm=(-100, -40), x_bin_server=1),
        WaterfallFrame(sequence=1, bins=(0, 0), dbm=(-40, -100), x_bin_server=1),
    ]

    assert average_dbm(frames) == (-70.0, -70.0)


def test_average_dbm_rejects_empty_and_ragged_input():
    with pytest.raises(ValueError, match="empty frame sequence"):
        average_dbm([])
    with pytest.raises(ValueError, match="inconsistent bin counts"):
        average_dbm([
            WaterfallFrame(sequence=0, bins=(0,), dbm=(-100,), x_bin_server=1),
            WaterfallFrame(sequence=1, bins=(0, 0), dbm=(-100, -100), x_bin_server=1),
        ])


def test_noise_floor_uses_the_median_so_carriers_do_not_raise_it():
    values = [-90.0] * 100 + [-20.0] * 5

    assert noise_floor_dbm(values) == -90.0


def test_find_peak_bin_searches_only_near_the_expected_position():
    values = [-90.0] * 100
    values[10] = -30.0
    values[80] = -10.0  # stronger, but far away

    assert find_peak_bin(values, 10, radius=4) == 10


def test_find_peak_bin_clamps_the_search_to_the_frame():
    values = [-90.0] * 10
    values[0] = -20.0

    assert find_peak_bin(values, 1, radius=5) == 0


def test_group_frames_by_window_groups_on_reported_window():
    frames = [_frame(100, 512), _frame(100, 512), _frame(101, 511)]

    grouped = group_frames_by_window(frames)

    assert sorted(grouped) == [100, 101]
    assert len(grouped[100]) == 2


def test_group_frames_by_window_rejects_frames_without_a_window():
    with pytest.raises(ValueError, match="no x_bin_server"):
        group_frames_by_window([WaterfallFrame(sequence=0, bins=(0,), dbm=(-90,))])


@pytest.mark.parametrize("true_offset", [0.0, 0.25, 0.5, 0.83, 0.895, 1.0, 1.5])
def test_sweep_recovers_a_planted_offset(true_offset):
    span, frames = _synthetic_sweep(true_offset)

    result = analyse_sweep_frames(frames, span=span, reference_hz=REFERENCE_HZ)
    low, high = result.offset_window()

    assert low < true_offset <= high
    # 40 positions at 1/32 bin each must beat the 0.133 bin bound from AM carriers.
    assert high - low < 0.05


def test_sweep_precision_matches_the_step_size():
    """The window should narrow to roughly one window position, not one bin."""
    span, frames = _synthetic_sweep(0.83)

    result = analyse_sweep_frames(frames, span=span, reference_hz=REFERENCE_HZ)
    low, high = result.offset_window()

    one_position_in_bins = span.unit_hz / span.bin_width_hz
    assert high - low == pytest.approx(one_position_in_bins, abs=1e-9)


def test_sweep_reports_crossing_a_bin_boundary():
    span, frames = _synthetic_sweep(0.83, steps=40)

    assert analyse_sweep_frames(frames, span=span, reference_hz=REFERENCE_HZ).crossed_bin_boundary()


def test_sweep_without_a_boundary_crossing_is_flagged_and_stays_wide():
    """Too short a sweep cannot beat a single measurement, and must say so."""
    span, frames = _synthetic_sweep(0.83, steps=4)

    result = analyse_sweep_frames(frames, span=span, reference_hz=REFERENCE_HZ)
    low, high = result.offset_window()

    assert not result.crossed_bin_boundary()
    assert high - low > 0.8, "without a crossing the bound should still be about one bin"


def test_sweep_ignores_positions_below_the_snr_threshold():
    span, frames = _synthetic_sweep(0.83)
    # Flatten one window into pure noise; its peak is meaningless.
    buried = [_frame(frames[0].x_bin_server, 0, peak_dbm=-90, floor_dbm=-90)]
    result = analyse_sweep_frames(buried + frames[1:], span=span, reference_hz=REFERENCE_HZ)

    assert len(result.usable(min_snr_db=6.0)) == len(frames) - 1
    low, high = result.offset_window(min_snr_db=6.0)
    assert low < 0.83 <= high


def test_sweep_raises_when_nothing_is_detected():
    span, _ = _synthetic_sweep(0.83)
    buried = [_frame(1000 + i, 512, peak_dbm=-90, floor_dbm=-90) for i in range(5)]

    result = analyse_sweep_frames(buried, span=span, reference_hz=REFERENCE_HZ)

    with pytest.raises(ValueError, match="was not detected"):
        result.offset_window(min_snr_db=6.0)


def test_sweep_raises_on_contradictory_samples():
    """A mis-specified reference makes the constraints inconsistent; say so plainly."""
    span = _span()
    samples = (
        SweepSample(x_bin_server=17170, frame_count=10, peak_bin=512, peak_dbm=-40, floor_dbm=-90),
        SweepSample(x_bin_server=17170, frame_count=10, peak_bin=400, peak_dbm=-40, floor_dbm=-90),
    )
    result = SweepResult(reference_hz=REFERENCE_HZ, span=span, samples=samples)

    with pytest.raises(ValueError, match="contradictory"):
        result.offset_window()


def test_sweep_works_at_several_zooms():
    """Positions per bin halve with each zoom step, so precision should track."""
    widths = {}
    for zoom in (8, 9, 10):
        positions_per_bin = 2 ** (14 - zoom)
        span, frames = _synthetic_sweep(0.83, zoom=zoom, steps=int(1.5 * positions_per_bin))
        result = analyse_sweep_frames(frames, span=span, reference_hz=REFERENCE_HZ)
        low, high = result.offset_window()
        assert low < 0.83 <= high
        widths[zoom] = high - low

    assert widths[8] < widths[9] < widths[10]


def test_summary_is_json_serialisable():
    import json

    span, frames = _synthetic_sweep(0.83)
    result = analyse_sweep_frames(frames, span=span, reference_hz=REFERENCE_HZ)

    payload = json.loads(json.dumps(result.summary()))

    assert payload["crossed_bin_boundary"] is True
    assert payload["offset_low"] < 0.83 <= payload["offset_high"]
    assert math.isfinite(payload["offset_width_hz"])


def test_sample_window_uses_averaged_not_peak_frames():
    """One noisy frame must not decide the peak; the average must."""
    span = _span()
    x_bin = round((REFERENCE_HZ - span.span_hz / 2) / span.unit_hz)
    naive = (REFERENCE_HZ - span.start_hz(x_bin)) / span.bin_width_hz
    true_bin = round(naive)

    # Nine clean frames, plus one where a noise spike two bins away is the
    # strongest thing in the frame. Max-hold would pick the spike; averaging
    # must not.
    frames = [_frame(x_bin, true_bin) for _ in range(9)]
    noisy = _frame(x_bin, true_bin + 2, peak_dbm=-20, floor_dbm=-90)

    sample = sample_window(x_bin, frames + [noisy], span=span, reference_hz=REFERENCE_HZ)

    assert sample.peak_bin == true_bin
    assert sample.frame_count == 10
