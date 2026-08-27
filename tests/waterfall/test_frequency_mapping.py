"""Fixture-backed W/F bin-to-frequency calibration.

These tests lock in the mapping derived from two local captures by checking it
against real AM broadcast carriers on their known 10 kHz channels. They need no
receiver and no network.
"""

from pathlib import Path

import pytest

from kiwi_client.fixtures import load_jsonl_events
from kiwi_client.protocol import parse_msg
from kiwi_client.waterfall import (
    WaterfallSessionMetadata,
    apply_span,
    parse_waterfall_uncompressed,
)

# (fixture, tuned centre kHz, expected zoom, AM channels inside the window)
CAPTURES = [
    ("tests/fixtures/kiwi/local-wf-910-zoom8.jsonl", 910.0, 8, range(860, 970, 10)),
    ("tests/fixtures/kiwi/local-wf-760-zoom9.jsonl", 760.0, 9, range(740, 790, 10)),
]


def _load(path: str):
    """Return (span, frames) for a captured W/F fixture."""
    metadata = WaterfallSessionMetadata()
    frames = []
    for event in load_jsonl_events(Path(path)):
        if event.type == "msg":
            metadata.observe(parse_msg(event.raw["text"]).params)
        elif event.type == "binary":
            frames.append(parse_waterfall_uncompressed(event.binary_payload))
    return metadata, frames


def _max_hold(frames):
    """Return the per-bin maximum across all frames; carriers are stable, noise is not."""
    width = len(frames[0].bins)
    return [max(frame.dbm[i] for frame in frames) for i in range(width)]


@pytest.mark.parametrize("path,center_khz,zoom,channels", CAPTURES)
def test_session_metadata_recovers_geometry(path, center_khz, zoom, channels):
    metadata, frames = _load(path)
    span = metadata.span()

    assert span is not None
    assert span.zoom == zoom
    assert span.bandwidth_hz == 30_000_000.0
    assert span.fft_size == 1024
    # x_bin_server in the frame header equals `MSG start`.
    assert frames[0].x_bin_server == metadata.start


@pytest.mark.parametrize("path,center_khz,zoom,channels", CAPTURES)
def test_window_center_reproduces_tuned_frequency(path, center_khz, zoom, channels):
    metadata, frames = _load(path)
    span = metadata.span()

    center_hz = span.center_hz(frames[0].x_bin_server)

    # Recovers the `cf` value that was tuned, to within a few Hz.
    assert center_hz == pytest.approx(center_khz * 1000, abs=5.0)


@pytest.mark.parametrize("path,center_khz,zoom,channels", CAPTURES)
def test_apply_span_fills_frame_frequency_fields(path, center_khz, zoom, channels):
    metadata, frames = _load(path)
    span = metadata.span()

    mapped = apply_span(frames[0], span)

    assert mapped.center_khz == pytest.approx(center_khz, abs=0.005)
    assert mapped.span_khz == pytest.approx(30_000.0 / 2**zoom)
    assert mapped.bin_width_hz == pytest.approx(30_000_000.0 / (1024 * 2**zoom))
    assert mapped.start_khz == pytest.approx(center_khz - mapped.span_khz / 2, abs=0.005)
    # Bins and dBm are carried through untouched.
    assert mapped.bins == frames[0].bins


@pytest.mark.parametrize("path,center_khz,zoom,channels", CAPTURES)
def test_known_am_carriers_land_on_predicted_bins(path, center_khz, zoom, channels):
    """Every 10 kHz AM channel in the window peaks at the bin the mapping predicts."""
    metadata, frames = _load(path)
    span = metadata.span()
    x_bin = frames[0].x_bin_server
    hold = _max_hold(frames)

    mismatches = []
    for khz in channels:
        predicted = round(span.bin_for_frequency(x_bin, khz * 1000))
        window = range(predicted - 3, predicted + 4)
        measured = max(window, key=lambda i: hold[i])
        if measured != predicted:
            mismatches.append((khz, predicted, measured))

    assert not mismatches, f"carriers not on predicted bins: {mismatches}"


@pytest.mark.parametrize("path,center_khz,zoom,channels", CAPTURES)
def test_carrier_peaks_stand_above_local_noise_floor(path, center_khz, zoom, channels):
    """Guards against the mapping test passing on noise rather than real carriers."""
    metadata, frames = _load(path)
    span = metadata.span()
    x_bin = frames[0].x_bin_server
    hold = _max_hold(frames)
    floor = sorted(hold)[len(hold) // 2]

    for khz in channels:
        peak_bin = round(span.bin_for_frequency(x_bin, khz * 1000))
        assert hold[peak_bin] > floor + 6, f"{khz} kHz is not clearly above the noise floor"


def test_bin_frequency_and_bin_for_frequency_round_trip():
    metadata, frames = _load(CAPTURES[0][0])
    span = metadata.span()
    x_bin = frames[0].x_bin_server

    for index in (0, 1, 511, 512, 1023):
        frequency = span.bin_frequency_hz(x_bin, index)
        assert span.bin_for_frequency(x_bin, frequency) == pytest.approx(index)


def test_sequence_stays_zero_across_a_full_capture():
    """Repeated seq=0 persists at 23 fps, so it is not a slow-rate artifact."""
    _, frames = _load(CAPTURES[0][0])

    assert len(frames) == 60
    assert {frame.sequence for frame in frames} == {0}
