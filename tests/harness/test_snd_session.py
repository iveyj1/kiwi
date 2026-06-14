from pathlib import Path

import pytest

from kiwi_client.fixtures import load_jsonl_events
from kiwi_client.protocol import parse_msg, parse_snd_uncompressed_mono
from kiwi_client.receiver_model import ReceiverState


FIXTURE = Path("tests/fixtures/kiwi/snd-session-basic.jsonl")


def test_snd_session_fixture_applies_msg_state_before_audio():
    state = ReceiverState()
    audio_frames = []

    for event in load_jsonl_events(FIXTURE):
        if event.type == "msg":
            state = state.apply_msg_params(parse_msg(event.raw["text"]).params)
        elif event.type == "binary":
            audio_frames.append(parse_snd_uncompressed_mono(event.binary_payload))

    assert state.audio_rate == 12000
    assert state.sample_rate == pytest.approx(12001.135)
    assert state.version_major == 1
    assert state.version_minor == 237
    assert state.kiwi_version == pytest.approx(1.237)
    assert state.bandwidth_hz == 30000000
    assert len(audio_frames) == 1
    assert audio_frames[0].seq == 1
