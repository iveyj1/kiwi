from pathlib import Path

import pytest

from kiwi_client.audio import SndSequenceTracker
from kiwi_client.fixtures import load_jsonl_events
from kiwi_client.protocol import parse_msg, parse_snd_uncompressed_mono
from kiwi_client.receiver_model import ReceiverState


FIXTURE = Path("tests/fixtures/kiwi/local-snd-5000-am-10khz.jsonl")


def test_local_snd_5000_am_10khz_capture_decodes_without_gaps():
    state = ReceiverState()
    tracker = SndSequenceTracker()
    frames = []
    statuses = []

    for event in load_jsonl_events(FIXTURE):
        if event.type == "msg":
            state = state.apply_msg_params(parse_msg(event.raw["text"]).params)
        elif event.type == "binary":
            frame = parse_snd_uncompressed_mono(event.binary_payload)
            frames.append(frame)
            statuses.append(tracker.observe(frame))

    assert state.sample_rate == pytest.approx(11998.94054)
    assert state.audio_rate == 12000
    assert state.version_major == 1
    assert state.version_minor == 842
    assert state.bandwidth_hz == 30000000
    assert len(frames) == 20
    assert [frame.seq for frame in frames] == list(range(1, 21))
    assert all(status.ok for status in statuses)
    assert all(len(frame.samples) == 512 for frame in frames)
