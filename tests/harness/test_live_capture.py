from pathlib import Path

import pytest

from kiwi_client.live_capture import LiveCaptureError, LiveSndCaptureConfig, keepalive_due, main


def test_keepalive_due_only_after_setup_and_interval():
    assert keepalive_due(100.0, 60.0, sent_setup=True)
    assert not keepalive_due(89.0, 60.0, sent_setup=True)
    assert not keepalive_due(100.0, 60.0, sent_setup=False)


def test_live_capture_config_rejects_non_allowed_receiver(tmp_path: Path):
    config = LiveSndCaptureConfig(host="example.com", port=8073, output=tmp_path / "x.jsonl")

    with pytest.raises(LiveCaptureError, match="allowed receivers"):
        config.validate()


def test_live_capture_config_can_allow_unrestricted_receiver_and_unlimited_limits(tmp_path: Path):
    config = LiveSndCaptureConfig(
        host="example.com",
        port=8073,
        output=tmp_path / "x.jsonl",
        receivers_restricted=False,
        duration_seconds=0,
        max_frames=0,
    )

    config.validate()


def test_live_capture_config_allows_about_one_minute(tmp_path: Path):
    config = LiveSndCaptureConfig(
        host="10.0.0.40",
        port=8073,
        output=tmp_path / "x.jsonl",
        duration_seconds=60,
        max_frames=1500,
    )

    config.validate()


def test_live_capture_config_rejects_negative_duration(tmp_path: Path):
    config = LiveSndCaptureConfig(host="10.0.0.40", port=8073, output=tmp_path / "x.jsonl", duration_seconds=-1)

    with pytest.raises(LiveCaptureError, match="duration"):
        config.validate()


def test_live_capture_config_rejects_existing_output_without_overwrite(tmp_path: Path):
    output = tmp_path / "x.jsonl"
    output.write_text("", encoding="utf-8")
    config = LiveSndCaptureConfig(host="10.0.0.40", port=8073, output=output)

    with pytest.raises(LiveCaptureError, match="output already exists"):
        config.validate()


def test_live_capture_dry_run_plan_has_local_uri_and_fixture_tested_commands(tmp_path: Path):
    config = LiveSndCaptureConfig(
        host="10.0.0.40",
        port=8073,
        output=tmp_path / "capture.jsonl",
        timestamp=123456,
    )

    config.validate()
    plan = config.dry_run_plan()

    assert plan["websocket_uri"] == "ws://10.0.0.40:8073/123456/SND"
    assert plan["initial_commands"] == ["SET auth t=kiwi p="]
    assert plan["dynamic_commands"] == [
        "SET AR OK in=<audio_rate> out=44100",
        "SET squelch=0 max=0",
        "SET genattn=0",
        "SET gen=0 mix=-1",
        "SET ident_user=kiwi-client",
        "SET mod=am low_cut=-4900 high_cut=4900 freq=4625.000",
        "SET agc=1 hang=0 thresh=-100 slope=6 decay=1000 manGain=50",
        "SET compression=0",
        "SET keepalive",
    ]


def test_live_capture_cli_dry_run_does_not_require_allow_live(tmp_path: Path, capsys):
    code = main([
        "--dry-run",
        "--host",
        "10.0.0.40",
        "--output",
        str(tmp_path / "capture.jsonl"),
        "--timestamp",
        "123456",
    ])

    captured = capsys.readouterr()
    assert code == 0
    assert "ws://10.0.0.40:8073/123456/SND" in captured.out


def test_live_capture_cli_refuses_without_allow_live(tmp_path: Path):
    with pytest.raises(SystemExit) as exc:
        main(["--host", "10.0.0.40", "--output", str(tmp_path / "capture.jsonl")])

    assert exc.value.code == 2
