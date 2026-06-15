from pathlib import Path

import pytest

from kiwi_client.fixtures import load_jsonl_events
from kiwi_client.live_capture import LiveCaptureError
from kiwi_client.live_play import LiveSndPlaybackConfig, apply_fade_in, apply_fade_out, main, play_replay_snd
from kiwi_client.playback import NullAudioSink
from kiwi_client.transport import ReplayTransport


FIXTURE = Path("tests/fixtures/kiwi/local-snd-5000-am-10khz.jsonl")


class RecordingSink(NullAudioSink):
    def __init__(self):
        super().__init__()
        self.payloads = []

    def write(self, pcm: bytes) -> None:
        self.payloads.append(pcm)
        super().write(pcm)


def _config() -> LiveSndPlaybackConfig:
    return LiveSndPlaybackConfig(
        host="10.0.0.40",
        port=8073,
        frequency_khz=5000.0,
        mode="am",
        low_cut_hz=-5000,
        high_cut_hz=5000,
        startup_mute_ms=0,
    )


def test_play_replay_snd_feeds_null_sink_from_live_fixture():
    transport = ReplayTransport(load_jsonl_events(FIXTURE))
    sink = NullAudioSink()
    metrics = []

    result = play_replay_snd(transport, sink, config=_config(), status_callback=metrics.append)

    assert transport.done
    assert result.sample_rate_hz == 11999
    assert result.frames == 20 * 512
    assert result.chunks == 20
    assert result.bytes_written == 20 * 512 * 2
    assert result.dry_run
    assert sink.started
    assert sink.stopped
    assert sink.chunks == 20
    assert len(metrics) == 20
    assert metrics[-1]["snd_seq"] == 20
    assert metrics[-1]["snd_frames"] == 20
    assert metrics[-1]["sample_rate_hz"] == 11999
    assert metrics[-1]["sequence_gaps"] == 0
    assert metrics[-1]["adc_overflows"] == 0
    assert "rssi_db" in metrics[-1]
    assert "smeter" in metrics[-1]


def test_play_replay_snd_drops_startup_audio_but_keeps_metrics():
    transport = ReplayTransport(load_jsonl_events(FIXTURE))
    sink = NullAudioSink()
    metrics = []
    config = _config()
    config = LiveSndPlaybackConfig(
        host=config.host,
        port=config.port,
        frequency_khz=config.frequency_khz,
        mode=config.mode,
        low_cut_hz=config.low_cut_hz,
        high_cut_hz=config.high_cut_hz,
        max_frames=20,
        startup_mute_ms=300,
    )

    result = play_replay_snd(transport, sink, config=config, status_callback=metrics.append)

    assert result.chunks == 20
    assert result.frames < 20 * 512
    assert result.bytes_written < 20 * 512 * 2
    assert sink.chunks < 20
    assert len(metrics) == 20
    assert metrics[-1]["snd_frames"] == 20


def test_play_replay_snd_applies_startup_fade_in():
    transport = ReplayTransport(load_jsonl_events(FIXTURE))
    sink = RecordingSink()
    config = LiveSndPlaybackConfig(
        host="10.0.0.40",
        port=8073,
        frequency_khz=5000.0,
        mode="am",
        low_cut_hz=-5000,
        high_cut_hz=5000,
        max_frames=2,
        startup_mute_ms=0,
        startup_fade_in_ms=20,
    )

    play_replay_snd(transport, sink, config=config)

    assert sink.payloads
    assert sink.payloads[0][:2] == b"\x00\x00"


def test_fade_helpers_shape_samples():
    faded_in, in_remaining = apply_fade_in((1000, 1000, 1000), fade_in_remaining=3, fade_in_total=3)
    faded_out, out_remaining = apply_fade_out((1000, 1000, 1000, 1000), fade_out_remaining=3, fade_out_total=3)

    assert faded_in == (0, 333, 666)
    assert in_remaining == 0
    assert faded_out == (1000, 666, 333)
    assert out_remaining == 0


def test_live_play_allows_about_one_minute():
    config = LiveSndPlaybackConfig(duration_seconds=60, max_frames=1500)

    config.validate()


def test_live_play_dry_run_plan_has_commands():
    config = LiveSndPlaybackConfig(timestamp=123456)

    plan = config.dry_run_plan()

    assert plan["websocket_uri"] == "ws://10.0.0.40:8073/123456/SND"
    assert plan["initial_commands"] == ["SET auth t=kiwi p="]
    assert "SET AR OK in=<audio_rate> out=44100" in plan["dynamic_commands"]
    assert "SET mod=am low_cut=-5000 high_cut=5000 freq=5000.000" in plan["dynamic_commands"]


def test_live_play_cli_refuses_without_allow_live():
    with pytest.raises(SystemExit) as exc:
        main(["--host", "10.0.0.40"])

    assert exc.value.code == 2


def test_live_play_cli_dry_run_does_not_connect(capsys):
    code = main(["--dry-run", "--host", "10.0.0.40", "--timestamp", "123456"])

    assert code == 0
    assert "ws://10.0.0.40:8073/123456/SND" in capsys.readouterr().out


def test_live_play_rejects_non_allowed_receiver():
    config = LiveSndPlaybackConfig(host="example.com")

    with pytest.raises(LiveCaptureError, match="allowed receivers"):
        config.validate()


def test_live_play_allows_unrestricted_receiver_and_unlimited_limits():
    config = LiveSndPlaybackConfig(host="example.com", receivers_restricted=False, duration_seconds=0, max_frames=0)

    config.validate()
