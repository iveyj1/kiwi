from pathlib import Path

import pytest

from kiwi_client.live_capture import LiveCaptureError, LiveSndCaptureConfig, main


def test_live_capture_config_rejects_non_local_receiver(tmp_path: Path):
    config = LiveSndCaptureConfig(host="example.com", port=8073, output=tmp_path / "x.jsonl")

    with pytest.raises(LiveCaptureError, match="local receivers"):
        config.validate()


def test_live_capture_config_rejects_long_duration(tmp_path: Path):
    config = LiveSndCaptureConfig(host="10.0.0.40", port=8073, output=tmp_path / "x.jsonl", duration_seconds=30)

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
    assert plan["commands"] == [
        "SET auth t=kiwi p=",
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
