from pathlib import Path

import pytest

from kiwi_client.fixtures import load_jsonl_events
from kiwi_client.protocol import KiwiProtocolError
from kiwi_client.waterfall import WaterfallFrame, WaterfallSequenceTracker, parse_waterfall_uncompressed, raw_sample_to_dbm


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
