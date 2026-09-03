from pathlib import Path

import pytest

from kiwi_client.fixtures import load_jsonl_events
from kiwi_client.protocol import parse_msg
from kiwi_client.waterfall import (
    WaterfallReceiverState,
    WaterfallSequenceTracker,
    contextualize_waterfall_frame,
    parse_waterfall_uncompressed,
)


FIXTURE = Path("tests/fixtures/kiwi/local-wf-5000-zoom0.jsonl")
AM_FIXTURE = Path("tests/fixtures/kiwi/local-wf-am-855-zoom7.jsonl")


def test_local_wf_5000_zoom0_capture_decodes_frames():
    events = load_jsonl_events(FIXTURE)
    binary_events = [event for event in events if event.type == "binary"]
    tracker = WaterfallSequenceTracker()

    frames = [parse_waterfall_uncompressed(event.binary_payload) for event in binary_events]
    statuses = [tracker.observe(frame) for frame in frames]

    assert len(frames) == 2
    assert [len(frame.bins) for frame in frames] == [1024, 1024]
    assert [frame.raw_flags for frame in frames] == [32, 32]
    assert [frame.x_bin_server for frame in frames] == [0, 0]
    assert [frame.flags_x_zoom_server for frame in frames] == [0, 0]
    assert [frame.sequence for frame in frames] == [0, 0]
    assert statuses[0].ok is True
    assert statuses[1].ok is True
    assert statuses[1].repeated_zero is True
    assert statuses[1].out_of_order is False


def test_local_wf_5000_zoom0_fixture_maps_to_full_receiver_bandwidth():
    events = load_jsonl_events(FIXTURE)
    state = WaterfallReceiverState()
    frames = []

    for event in events:
        if event.type == "msg":
            state = state.apply_msg_params(parse_msg(event.raw["text"]).params)
        elif event.type == "binary":
            frames.append(contextualize_waterfall_frame(parse_waterfall_uncompressed(event.binary_payload), state))

    assert state.bandwidth_hz == 30_000_000
    assert state.wf_fft_size == 1024
    assert state.zoom_max == 14
    assert frames[0].start_khz == 0.0
    assert frames[0].center_khz == 15000.0
    assert frames[0].span_khz == 30000.0
    assert frames[0].bin_width_hz == 30000000 / 1024


def test_local_wf_am_zoom7_fixture_maps_known_760_and_950_khz_carriers():
    events = load_jsonl_events(AM_FIXTURE)
    state = WaterfallReceiverState()
    frames = []

    for event in events:
        if event.type == "msg":
            state = state.apply_msg_params(parse_msg(event.raw["text"]).params)
        elif event.type == "binary":
            frames.append(contextualize_waterfall_frame(parse_waterfall_uncompressed(event.binary_payload), state))

    assert len(frames) == 5
    frame = frames[-1]
    assert frame.start_khz == pytest.approx(737.8113269805908)
    assert frame.center_khz == pytest.approx(854.9988269805908)
    assert frame.span_khz == pytest.approx(234.375)
    assert frame.bin_width_hz == pytest.approx(228.8818359375)

    average_dbm = [sum(item.dbm[index] for item in frames) / len(frames) for index in range(1024)]

    def strongest_near(target_khz: float, radius_bins: int = 4) -> tuple[float, float]:
        target_bin = round((target_khz - frame.start_khz) * 1000 / frame.bin_width_hz - 0.5)
        candidates = range(target_bin - radius_bins, target_bin + radius_bins + 1)
        peak_bin = max(candidates, key=lambda index: average_dbm[index])
        frequency_khz = frame.start_khz + (peak_bin + 0.5) * frame.bin_width_hz / 1000
        return frequency_khz, average_dbm[peak_bin]

    peak_760_khz, power_760_dbm = strongest_near(760.0)
    peak_950_khz, power_950_dbm = strongest_near(950.0)

    assert peak_760_khz == pytest.approx(760.127, abs=0.25)
    assert peak_950_khz == pytest.approx(949.870, abs=0.25)
    assert power_760_dbm > -25
    assert power_950_dbm > -35
