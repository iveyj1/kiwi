from pathlib import Path

from kiwi_client.live_waterfall import LiveWaterfallCaptureConfig
from kiwi_client.live_waterfall_preview import main, preview_live_waterfall
from tests.harness.test_live_waterfall import FakeConnect, WF_PAYLOAD


def test_preview_live_waterfall_prints_ascii_rows_with_fake_websocket(tmp_path: Path):
    output = tmp_path / "wf.jsonl"
    config = LiveWaterfallCaptureConfig(host="10.0.0.40", port=8073, output=output, timestamp=123456, max_frames=1)
    fake_connect = FakeConnect([WF_PAYLOAD])
    rows = []

    path = preview_live_waterfall(config, allow_live=True, websocket_connect=fake_connect, row_callback=rows.append)

    assert path == output
    assert rows == ["   +@"]


def test_live_waterfall_preview_main_dry_run(capsys):
    code = main(["--dry-run", "--host", "10.0.0.40", "--timestamp", "123456"])

    captured = capsys.readouterr()
    assert code == 0
    assert "ws://10.0.0.40:8073/123456/W/F" in captured.out


def test_live_waterfall_preview_main_uses_save_fixture_with_fake_websocket(tmp_path: Path, monkeypatch, capsys):
    output = tmp_path / "wf.jsonl"
    fake_connect = FakeConnect([WF_PAYLOAD])

    monkeypatch.setattr("kiwi_client.live_waterfall_preview._websocket_connect_for_main", lambda: fake_connect)
    code = main([
        "--allow-live",
        "--host",
        "10.0.0.40",
        "--timestamp",
        "123456",
        "--max-frames",
        "1",
        "--save-fixture",
        str(output),
    ])

    captured = capsys.readouterr()
    assert code == 0
    assert captured.out == "   +@\n"
    assert output.exists()
