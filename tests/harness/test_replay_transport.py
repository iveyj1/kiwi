from pathlib import Path

import pytest

from kiwi_client.capture import JsonlCaptureWriter, SndCaptureMetadata
from kiwi_client.commands import encode_auth, encode_basic_snd_setup
from kiwi_client.fixtures import load_jsonl_events
from kiwi_client.protocol import parse_msg, parse_snd_uncompressed_mono
from kiwi_client.receiver_model import ReceiverState
from kiwi_client.transport import ReplayTransport, ReplayTransportError


SND_PAYLOAD = bytes.fromhex("534e44000100000003528000ffff000000017fff")


def _write_script(path: Path) -> None:
    writer = JsonlCaptureWriter(
        SndCaptureMetadata(
            receiver="offline-replay",
            utc_time="2026-06-13T00:00:00Z",
            local_time="2026-06-12T17:00:00-07:00",
            frequency_khz=4625.0,
            mode="am",
            low_cut_hz=-4900,
            high_cut_hz=4900,
            compression=False,
            notes="offline replay test",
        )
    )
    for index, command in enumerate([encode_auth()] + encode_basic_snd_setup(user="kiwi-client", frequency_khz=4625.0)):
        writer.add_tx_cmd(index * 0.001, command)
    writer.add_rx_msg(0.100, "MSG sample_rate=12001.135 audio_rate=12000")
    writer.add_rx_binary(0.110, SND_PAYLOAD)
    writer.write(path)


def test_replay_transport_validates_commands_and_returns_rx_events(tmp_path: Path):
    path = tmp_path / "script.jsonl"
    _write_script(path)
    transport = ReplayTransport(load_jsonl_events(path))

    for command in [encode_auth()] + encode_basic_snd_setup(user="kiwi-client", frequency_khz=4625.0):
        transport.send(command)

    state = ReceiverState().apply_msg_params(parse_msg(transport.receive().text or "").params)
    frame = parse_snd_uncompressed_mono(transport.receive().payload or b"")

    assert transport.done
    assert state.sample_rate == 12001.135
    assert frame.seq == 1


def test_replay_transport_rejects_command_mismatch(tmp_path: Path):
    path = tmp_path / "script.jsonl"
    _write_script(path)
    transport = ReplayTransport(load_jsonl_events(path))

    with pytest.raises(ReplayTransportError, match="sent command mismatch"):
        transport.send("SET keepalive")
