from pathlib import Path

import pytest

from kiwi_client.fixtures import load_jsonl_events
from kiwi_client.protocol import KiwiProtocolError
from kiwi_client.waterfall import (
    WaterfallFrame,
    WaterfallReceiverState,
    WaterfallSequenceTracker,
    contextualize_waterfall_frame,
    decode_waterfall_interpolation,
    parse_waterfall_uncompressed,
    raw_sample_to_dbm,
)


FIXTURE = Path("tests/fixtures/kiwi/wf-basic.jsonl")


def _fixture_payload() -> bytes:
    events = load_jsonl_events(FIXTURE)
    [event] = [event for event in events if event.type == "binary"]
    return event.binary_payload


def test_wf_uncompressed_header_fields():
    frame = parse_waterfall_uncompressed(_fixture_payload())

    assert frame.sequence == 42
    assert frame.x_bin_server == 7
    assert frame.flags_x_zoom_server == 0x00020003
    assert frame.raw_flags == 0


def test_wf_uncompressed_bins_and_dbm_mapping():
    frame = parse_waterfall_uncompressed(_fixture_payload())

    assert frame.bins == (0, 55, 128, 200, 255)
    assert frame.dbm == (-255, -200, -127, -55, 0)
    assert raw_sample_to_dbm(128) == -127


@pytest.mark.parametrize(
    ("value", "method", "cic_compensation"),
    [
        (0, "max", False),
        (1, "min", False),
        (2, "last", False),
        (3, "drop", False),
        (4, "cma", False),
        (10, "max", True),
        (11, "min", True),
        (12, "last", True),
        (13, "drop", True),
        (14, "cma", True),
    ],
)
def test_wf_interpolation_values_are_categorical_modes(value, method, cic_compensation):
    interpolation = decode_waterfall_interpolation(value)

    assert interpolation.value == value
    assert interpolation.method == method
    assert interpolation.cic_compensation is cic_compensation


def test_wf_interpolation_rejects_unsupported_gap_values():
    with pytest.raises(ValueError, match="0..4 or 10..14"):
        decode_waterfall_interpolation(5)


def test_wf_receiver_state_maps_zoomed_max_bin_grid_to_frequency():
    state = WaterfallReceiverState(
        bandwidth_hz=30_000_000,
        wf_fft_size=1024,
        zoom_max=14,
    )
    max_bins = 1024 << 14
    raw = WaterfallFrame(
        sequence=1,
        bins=(0,) * 1024,
        dbm=(-100,) * 1024,
        x_bin_server=max_bins // 4,
        flags_x_zoom_server=0x00010002,
    )

    frame = contextualize_waterfall_frame(raw, state)

    assert frame.start_khz == pytest.approx(7500.0)
    assert frame.span_khz == pytest.approx(7500.0)
    assert frame.center_khz == pytest.approx(11250.0)
    assert frame.bin_width_hz == pytest.approx(7500_000 / 1024)


def test_wf_receiver_state_applies_metadata_messages():
    state = WaterfallReceiverState().apply_msg_params(
        {
            "bandwidth": "30000000",
            "center_freq": "15000000",
            "wf_fft_size": "1024",
            "wf_fps": "13",
            "wf_fps_max": "23",
            "zoom_max": "14",
            "wf_cal": "-13",
            "zoom": "3",
            "start": "1234",
        }
    )

    assert state.bandwidth_hz == 30_000_000
    assert state.center_freq_hz == 15_000_000
    assert state.wf_fft_size == 1024
    assert state.wf_fps == 13
    assert state.wf_fps_max == 23
    assert state.zoom_max == 14
    assert state.wf_cal_db == -13
    assert state.zoom == 3
    assert state.start_bin == 1234


def test_wf_rejects_non_wf_tag():
    with pytest.raises(KiwiProtocolError, match="expected W/F tag"):
        parse_waterfall_uncompressed(b"SND\x00" + b"\x00" * 12)


def test_wf_rejects_truncated_header():
    with pytest.raises(KiwiProtocolError, match="shorter than 13-byte"):
        parse_waterfall_uncompressed(b"W/F\x00\x01\x02")


def test_wf_rejects_empty_bins():
    payload = b"W/F\x00" + (7).to_bytes(4, "little") + (0).to_bytes(4, "little") + (42).to_bytes(4, "little")

    with pytest.raises(KiwiProtocolError, match="contains no bin data"):
        parse_waterfall_uncompressed(payload)


def test_wf_rejects_raw_sample_out_of_range():
    with pytest.raises(ValueError, match="raw waterfall sample"):
        raw_sample_to_dbm(256)


def test_wf_sequence_tracker_detects_gap():
    tracker = WaterfallSequenceTracker()

    first = tracker.observe(WaterfallFrame(sequence=1, bins=(0,), dbm=(-255,)))
    second = tracker.observe(WaterfallFrame(sequence=3, bins=(0,), dbm=(-255,)))

    assert first.ok is True
    assert first.expected_seq is None
    assert second.ok is False
    assert second.expected_seq == 2
    assert second.missing_count == 1


def test_wf_sequence_tracker_handles_wraparound():
    tracker = WaterfallSequenceTracker()

    first = tracker.observe(WaterfallFrame(sequence=0xFFFFFFFF, bins=(0,), dbm=(-255,)))
    second = tracker.observe(WaterfallFrame(sequence=0, bins=(0,), dbm=(-255,)))

    assert first.ok is True
    assert second.ok is True
    assert second.expected_seq == 0


def test_wf_sequence_tracker_marks_out_of_order():
    tracker = WaterfallSequenceTracker()
    tracker.observe(WaterfallFrame(sequence=10, bins=(0,), dbm=(-255,)))

    status = tracker.observe(WaterfallFrame(sequence=9, bins=(0,), dbm=(-255,)))

    assert status.ok is False
    assert status.expected_seq == 11
    assert status.out_of_order is True
    assert status.missing_count == 0


def test_wf_sequence_tracker_treats_repeated_zero_as_inactive_sequence():
    tracker = WaterfallSequenceTracker()
    tracker.observe(WaterfallFrame(sequence=0, bins=(0,), dbm=(-255,)))

    status = tracker.observe(WaterfallFrame(sequence=0, bins=(0,), dbm=(-255,)))

    assert status.ok is True
    assert status.expected_seq == 1
    assert status.repeated_zero is True
    assert status.out_of_order is False
    assert status.missing_count == 0
