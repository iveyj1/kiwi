from pathlib import Path

import pytest

from kiwi_client.playback import NullAudioSink, SoundDeviceSink, main, play_wav_file, samples_to_pcm16le
from kiwi_client.recorder import write_snd_fixture_wav


FIXTURE = Path("tests/fixtures/kiwi/local-snd-5000-am-10khz.jsonl")


def _wav(tmp_path: Path) -> Path:
    path = tmp_path / "playback.wav"
    write_snd_fixture_wav(FIXTURE, path)
    return path


def test_play_wav_file_feeds_null_sink(tmp_path: Path):
    path = _wav(tmp_path)
    sink = NullAudioSink()

    result = play_wav_file(path, sink, chunk_frames=2048)

    assert result.sample_rate_hz == 11999
    assert result.channels == 1
    assert result.sample_width_bytes == 2
    assert result.frames == 10240
    assert result.chunks == 5
    assert result.bytes_written == 10240 * 2
    assert sink.started
    assert sink.stopped
    assert sink.chunks == 5
    assert sink.bytes_written == 10240 * 2


def test_playback_cli_dry_run_outputs_json(tmp_path: Path, capsys):
    path = _wav(tmp_path)

    code = main([str(path), "--dry-run", "--json", "--chunk-frames", "2048"])

    out = capsys.readouterr().out
    assert code == 0
    assert '"sample_rate_hz": 11999' in out
    assert '"chunks": 5' in out


def test_samples_to_pcm16le():
    assert samples_to_pcm16le((-32768, -1, 0, 1, 32767)).hex() == "0080ffff00000100ff7f"


def test_sounddevice_sink_rejects_non_16_bit_before_importing_backend():
    with pytest.raises(ValueError, match="16-bit"):
        SoundDeviceSink().start(sample_rate_hz=12000, channels=1, sample_width_bytes=1)
