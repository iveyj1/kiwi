import asyncio
import json
from pathlib import Path

import pytest

from kiwi_client.fixtures import load_jsonl_events
from kiwi_client.live_capture import LiveCaptureError
from kiwi_client.live_waterfall import LiveWaterfallCaptureConfig, capture_live_waterfall, main

WF_PAYLOAD = b"W/F\x00" + (7).to_bytes(4, "little") + (0x00020003).to_bytes(4, "little") + (42).to_bytes(4, "little") + bytes([0, 55, 128, 200, 255])


class FakeWaterfallWebSocket:
    def __init__(self, messages):
        self.messages = list(messages)
        self.sent = []

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def send(self, command):
        self.sent.append(command)

    async def recv(self):
        if not self.messages:
            await asyncio.sleep(1)
        return self.messages.pop(0)


class FakeConnect:
    def __init__(self, messages):
        self.websocket = FakeWaterfallWebSocket(messages)
        self.calls = []

    def __call__(self, uri, **kwargs):
        self.calls.append((uri, kwargs))
        return self.websocket


def test_live_waterfall_config_dry_run_plan(tmp_path: Path):
    config = LiveWaterfallCaptureConfig(host="10.0.0.40", port=8073, output=tmp_path / "wf.jsonl", timestamp=123456)

    config.validate()
    plan = config.dry_run_plan()

    assert plan["websocket_uri"] == "ws://10.0.0.40:8073/123456/W/F"
    assert plan["render_mindb"] == -110
    assert plan["render_maxdb"] == 0
    assert plan["ascii_ramp"] == " .:-=+*#%@"
    assert plan["commands"] == [
        "SET auth t=kiwi p=",
        "SET zoom=0 cf=5000.000",
        "SET maxdb=0 mindb=-110",
        "SET wf_speed=1",
        "SET wf_comp=0",
        "SET interp=13",
        "SET keepalive",
    ]


def test_live_waterfall_config_rejects_non_allowed_receiver(tmp_path: Path):
    config = LiveWaterfallCaptureConfig(host="example.com", port=8073, output=tmp_path / "wf.jsonl")

    with pytest.raises(LiveCaptureError, match="allowed receivers"):
        config.validate()


def test_live_waterfall_cli_dry_run_does_not_require_allow_live(tmp_path: Path, capsys):
    code = main([
        "--dry-run",
        "--host",
        "10.0.0.40",
        "--output",
        str(tmp_path / "wf.jsonl"),
        "--timestamp",
        "123456",
    ])

    captured = capsys.readouterr()
    assert code == 0
    assert "ws://10.0.0.40:8073/123456/W/F" in captured.out


def test_live_waterfall_cli_refuses_without_allow_live(tmp_path: Path):
    with pytest.raises(SystemExit) as exc:
        main(["--host", "10.0.0.40", "--output", str(tmp_path / "wf.jsonl")])

    assert exc.value.code == 2


def test_capture_live_waterfall_writes_fixture_with_fake_websocket(tmp_path: Path):
    output = tmp_path / "wf.jsonl"
    config = LiveWaterfallCaptureConfig(host="10.0.0.40", port=8073, output=output, timestamp=123456, max_frames=1)
    fake_connect = FakeConnect([b"MSG wf_setup=1", WF_PAYLOAD])
    metrics = []

    path = asyncio.run(capture_live_waterfall(config, allow_live=True, websocket_connect=fake_connect, status_callback=metrics.append))

    events = load_jsonl_events(path)
    raw_events = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
    assert path == output
    assert fake_connect.calls[0][0] == "ws://10.0.0.40:8073/123456/W/F"
    assert fake_connect.websocket.sent == config.dry_run_plan()["commands"]
    assert raw_events[0]["dir"] == "meta"
    assert raw_events[0]["stream"] == "wf"
    assert [event.raw["text"] for event in events if event.dir == "tx"] == config.dry_run_plan()["commands"]
    assert [event.binary_payload for event in events if event.type == "binary"] == [WF_PAYLOAD]
    assert metrics[-1]["wf_seq"] == 42
    assert metrics[-1]["wf_frames"] == 1
    assert metrics[-1]["ascii_row"] == "   +@"


def test_capture_live_waterfall_uses_separate_ascii_render_scale(tmp_path: Path):
    output = tmp_path / "wf.jsonl"
    config = LiveWaterfallCaptureConfig(
        host="10.0.0.40",
        port=8073,
        output=output,
        timestamp=123456,
        max_frames=1,
        render_mindb=-255,
        render_maxdb=0,
    )
    fake_connect = FakeConnect([WF_PAYLOAD])
    metrics = []

    asyncio.run(capture_live_waterfall(config, allow_live=True, websocket_connect=fake_connect, status_callback=metrics.append))

    assert metrics[-1]["ascii_row"] == " :+#@"
