from pathlib import Path
import wave

from kiwi_client.fixtures import load_jsonl_events
from kiwi_client.recorder import SndWavRecorder, main, write_snd_fixture_wav


FIXTURE = Path("tests/fixtures/kiwi/local-snd-5000-am-10khz.jsonl")


def test_write_snd_fixture_wav_from_local_capture(tmp_path: Path):
    output = tmp_path / "local-snd-5000-am-10khz.wav"

    result = write_snd_fixture_wav(FIXTURE, output)

    assert result.path == output
    assert result.sample_rate_hz == 11999
    assert result.channels == 1
    assert result.sample_width_bytes == 2
    assert result.snd_frames == 20
    assert result.frames == 20 * 512
    assert result.sequence_gaps == 0

    with wave.open(str(output), "rb") as wav:
        assert wav.getnchannels() == 1
        assert wav.getsampwidth() == 2
        assert wav.getframerate() == 11999
        assert wav.getnframes() == 20 * 512
        assert len(wav.readframes(wav.getnframes())) == 20 * 512 * 2


def test_snd_wav_recorder_exposes_status_metrics_from_fixture():
    recorder = SndWavRecorder()

    for event in load_jsonl_events(FIXTURE):
        if event.type == "msg":
            recorder.add_msg(event.raw["text"])
        elif event.type == "binary":
            recorder.add_snd_payload(event.binary_payload)

    metrics = recorder.status_metrics()
    assert metrics["sample_rate_hz"] == 11999
    assert metrics["snd_frames"] == 20
    assert metrics["snd_seq"] == 20
    assert metrics["sequence_gaps"] == 0
    assert metrics["adc_overflows"] == 0
    assert "rssi_db" in metrics
    assert "smeter" in metrics


def test_fixture_to_wav_cli_writes_summary_json(tmp_path: Path, capsys):
    output = tmp_path / "cli.wav"

    code = main([str(FIXTURE), str(output), "--json"])

    captured = capsys.readouterr()
    assert code == 0
    assert '"sample_rate_hz": 11999' in captured.out
    assert '"frames": 10240' in captured.out
    assert output.exists()
