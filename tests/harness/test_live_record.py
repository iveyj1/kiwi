from pathlib import Path
import wave

import pytest

from kiwi_client.fixtures import load_jsonl_events
from kiwi_client.live_capture import LiveCaptureError
from kiwi_client.live_record import LiveSndWavRecordConfig, main, record_replay_snd_wav
from kiwi_client.transport import ReplayTransport


FIXTURE = Path("tests/fixtures/kiwi/local-snd-5000-am-10khz.jsonl")


def _config(output: Path) -> LiveSndWavRecordConfig:
    return LiveSndWavRecordConfig(
        host="10.0.0.40",
        port=8073,
        output=output,
        frequency_khz=5000.0,
        mode="am",
        low_cut_hz=-5000,
        high_cut_hz=5000,
        overwrite=True,
    )


def test_record_replay_snd_wav_uses_live_fixture_command_flow(tmp_path: Path):
    output = tmp_path / "direct.wav"
    transport = ReplayTransport(load_jsonl_events(FIXTURE))

    result = record_replay_snd_wav(transport, output, config=_config(output))

    assert transport.done
    assert result.sample_rate_hz == 11999
    assert result.snd_frames == 20
    assert result.frames == 20 * 512
    assert result.sequence_gaps == 0
    with wave.open(str(output), "rb") as wav:
        assert wav.getnchannels() == 1
        assert wav.getsampwidth() == 2
        assert wav.getframerate() == 11999
        assert wav.getnframes() == 20 * 512


def test_live_record_dry_run_plan_has_wav_output_and_commands(tmp_path: Path):
    config = LiveSndWavRecordConfig(
        host="10.0.0.40",
        port=8073,
        output=tmp_path / "direct.wav",
        frequency_khz=5000.0,
        mode="am",
        low_cut_hz=-5000,
        high_cut_hz=5000,
        timestamp=123456,
    )

    plan = config.dry_run_plan()

    assert plan["websocket_uri"] == "ws://10.0.0.40:8073/123456/SND"
    assert plan["output"].endswith("direct.wav")
    assert plan["initial_commands"] == ["SET auth t=kiwi p="]
    assert "SET AR OK in=<audio_rate> out=44100" in plan["dynamic_commands"]
    assert "SET mod=am low_cut=-5000 high_cut=5000 freq=5000.000" in plan["dynamic_commands"]


def test_live_record_cli_refuses_without_allow_live(tmp_path: Path):
    with pytest.raises(SystemExit) as exc:
        main(["--host", "10.0.0.40", "--output", str(tmp_path / "direct.wav")])

    assert exc.value.code == 2


def test_live_record_cli_dry_run_does_not_connect(tmp_path: Path, capsys):
    code = main([
        "--dry-run",
        "--host",
        "10.0.0.40",
        "--output",
        str(tmp_path / "direct.wav"),
        "--timestamp",
        "123456",
    ])

    assert code == 0
    assert "ws://10.0.0.40:8073/123456/SND" in capsys.readouterr().out


def test_live_record_rejects_non_local_receiver(tmp_path: Path):
    config = LiveSndWavRecordConfig(host="example.com", port=8073, output=tmp_path / "x.wav")

    with pytest.raises(LiveCaptureError, match="local receivers"):
        config.validate()
