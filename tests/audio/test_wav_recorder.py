from pathlib import Path
import wave

from kiwi_client.recorder import write_snd_fixture_wav


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
