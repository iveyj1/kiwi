from pathlib import Path

import pytest

from kiwi_client.fixtures import load_jsonl_events
from kiwi_client.live_capture import LiveCaptureError
from kiwi_client.live_play import LiveSndPlaybackConfig, main, play_replay_snd
from kiwi_client.playback import NullAudioSink
from kiwi_client.transport import ReplayTransport


FIXTURE = Path("tests/fixtures/kiwi/local-snd-5000-am-10khz.jsonl")


def _config() -> LiveSndPlaybackConfig:
    return LiveSndPlaybackConfig(
        host="10.0.0.40",
        port=8073,
        frequency_khz=5000.0,
        mode="am",
        low_cut_hz=-5000,
        high_cut_hz=5000,
    )


def test_play_replay_snd_feeds_null_sink_from_live_fixture():
    transport = ReplayTransport(load_jsonl_events(FIXTURE))
    sink = NullAudioSink()

    result = play_replay_snd(transport, sink, config=_config())

    assert transport.done
    assert result.sample_rate_hz == 11999
    assert result.frames == 20 * 512
    assert result.chunks == 20
    assert result.bytes_written == 20 * 512 * 2
    assert result.dry_run
    assert sink.started
    assert sink.stopped
    assert sink.chunks == 20


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


def test_live_play_rejects_non_local_receiver():
    config = LiveSndPlaybackConfig(host="example.com")

    with pytest.raises(LiveCaptureError, match="local receivers"):
        config.validate()
