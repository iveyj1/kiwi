from pathlib import Path

from kiwi_client.capture import JsonlCaptureWriter, SndCaptureMetadata
from kiwi_client.commands import encode_auth, encode_basic_snd_setup
from kiwi_client.fixtures import load_jsonl_events
from kiwi_client.protocol import parse_msg, parse_snd_uncompressed_mono
from kiwi_client.receiver_model import ReceiverState


SND_PAYLOAD = bytes.fromhex("534e44000100000003528000ffff000000017fff")


def _metadata() -> SndCaptureMetadata:
    return SndCaptureMetadata(
        receiver="10.0.0.40:8073",
        utc_time="2026-06-13T00:00:00Z",
        local_time="2026-06-12T17:00:00-07:00",
        frequency_khz=4625.0,
        mode="am",
        low_cut_hz=-4900,
        high_cut_hz=4900,
        compression=False,
        notes="offline writer test; not a live capture",
    )


def test_capture_writer_round_trips_commands_msg_and_binary(tmp_path: Path):
    writer = JsonlCaptureWriter(_metadata())
    for index, command in enumerate([encode_auth()] + encode_basic_snd_setup(user="kiwi-client", frequency_khz=4625.0)):
        writer.add_tx_cmd(index * 0.001, command)
    writer.add_rx_msg(0.100, "MSG sample_rate=12001.135 audio_rate=12000")
    writer.add_rx_binary(0.110, SND_PAYLOAD)

    path = tmp_path / "capture" / "snd-capture.jsonl"
    writer.write(path)

    events = load_jsonl_events(path)
    assert [event.type for event in events[:6]] == ["cmd"] * 6
    assert events[0].raw["text"] == "SET auth t=kiwi p="

    state = ReceiverState()
    audio_frames = []
    for event in events:
        if event.type == "msg":
            state = state.apply_msg_params(parse_msg(event.raw["text"]).params)
        elif event.type == "binary":
            audio_frames.append(parse_snd_uncompressed_mono(event.binary_payload))

    assert state.sample_rate == 12001.135
    assert state.audio_rate == 12000
    assert len(audio_frames) == 1
    assert audio_frames[0].samples == (-32768, -1, 0, 1, 32767)
