from pathlib import Path

from kiwi_client.fixtures import load_jsonl_events
from kiwi_client.waterfall import WaterfallSequenceTracker, parse_waterfall_uncompressed


FIXTURE = Path("tests/fixtures/kiwi/local-wf-5000-zoom0.jsonl")


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
