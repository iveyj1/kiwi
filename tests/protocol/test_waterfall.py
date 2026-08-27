from pathlib import Path

import pytest

from kiwi_client.fixtures import load_jsonl_events
from kiwi_client.protocol import KiwiProtocolError
from kiwi_client.waterfall import (
    WaterfallFrame,
    WaterfallSequenceTracker,
    WaterfallSessionMetadata,
    WaterfallSpan,
    apply_span,
    parse_waterfall_uncompressed,
    raw_sample_to_dbm,
    zoom_from_flags,
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


def test_waterfall_span_derives_geometry_from_bandwidth_and_zoom():
    span = WaterfallSpan(bandwidth_hz=30_000_000.0, zoom=8)

    assert span.unit_hz == pytest.approx(1.7881393432617188)
    assert span.bin_width_hz == pytest.approx(114.44091796875)
    assert span.span_hz == pytest.approx(117_187.5)


def test_waterfall_span_zoom_zero_matches_first_local_fixture():
    span = WaterfallSpan(bandwidth_hz=30_000_000.0, zoom=0)

    assert span.span_hz == pytest.approx(30_000_000.0)
    assert span.bin_width_hz == pytest.approx(29_296.875)
    assert span.start_hz(0) == 0.0


def test_waterfall_span_window_center_ignores_bin_center_offset():
    """Window geometry reports what was tuned; only bin mapping carries the offset."""
    span = WaterfallSpan(bandwidth_hz=30_000_000.0, zoom=8)

    center = span.center_hz(476140)
    edge = span.start_hz(476140)

    assert center - edge == pytest.approx(span.span_hz / 2)
    assert center == pytest.approx(910_000.0, abs=5.0)


def test_waterfall_span_bin_frequency_applies_center_offset():
    span = WaterfallSpan(bandwidth_hz=30_000_000.0, zoom=8, bin_center_offset=0.0)
    shifted = WaterfallSpan(bandwidth_hz=30_000_000.0, zoom=8, bin_center_offset=0.83)

    difference = shifted.bin_frequency_hz(476140, 100) - span.bin_frequency_hz(476140, 100)

    assert difference == pytest.approx(0.83 * span.bin_width_hz)


def test_waterfall_span_rejects_invalid_geometry():
    with pytest.raises(ValueError, match="bandwidth must be positive"):
        WaterfallSpan(bandwidth_hz=0.0, zoom=0)
    with pytest.raises(ValueError, match="FFT size must be >= 1"):
        WaterfallSpan(bandwidth_hz=30_000_000.0, zoom=0, fft_size=0)
    with pytest.raises(ValueError, match="zoom must be >= 0"):
        WaterfallSpan(bandwidth_hz=30_000_000.0, zoom=-1)
    with pytest.raises(ValueError, match="exceeds zoom_max"):
        WaterfallSpan(bandwidth_hz=30_000_000.0, zoom=15, zoom_max=14)


def test_waterfall_session_metadata_accumulates_across_msg_frames():
    metadata = WaterfallSessionMetadata()

    assert metadata.span() is None
    metadata.observe({"center_freq": "15000000", "bandwidth": "30000000"})
    assert metadata.span() is None, "zoom is still unknown"
    metadata.observe({"wf_fft_size": "1024", "zoom_max": "14", "wf_cal": "-13"})
    metadata.observe({"zoom": "8", "start": "476140"})

    span = metadata.span()
    assert span.bandwidth_hz == 30_000_000.0
    assert span.zoom == 8
    assert span.fft_size == 1024
    assert span.zoom_max == 14
    assert metadata.start == 476140


def test_waterfall_session_metadata_ignores_unrelated_parameters():
    metadata = WaterfallSessionMetadata()
    metadata.observe({"bandwidth": "30000000", "zoom": "4"})
    metadata.observe({"wf_fps": "23", "rx_chans": "8"})

    assert metadata.span().zoom == 4


def test_zoom_from_flags_reads_low_bits():
    assert zoom_from_flags(8) == 8
    assert zoom_from_flags(0x40009) == 9


def test_apply_span_fills_frequency_fields():
    frame = WaterfallFrame(sequence=0, bins=(0, 128), dbm=(-255, -127), x_bin_server=476140)
    span = WaterfallSpan(bandwidth_hz=30_000_000.0, zoom=8)

    mapped = apply_span(frame, span)

    assert mapped.center_khz == pytest.approx(910.0, abs=0.005)
    assert mapped.span_khz == pytest.approx(117.1875)
    assert mapped.bin_width_hz == pytest.approx(114.44091796875)
    assert mapped.bins == frame.bins
    assert mapped.sequence == frame.sequence


def test_apply_span_requires_x_bin_server():
    frame = WaterfallFrame(sequence=0, bins=(0,), dbm=(-255,))
    span = WaterfallSpan(bandwidth_hz=30_000_000.0, zoom=8)

    with pytest.raises(ValueError, match="no x_bin_server"):
        apply_span(frame, span)
