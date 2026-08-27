import asyncio
import json
import queue
from pathlib import Path

import pytest
from websockets.exceptions import ConnectionClosedError

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
        message = self.messages.pop(0)
        if isinstance(message, BaseException):
            raise message
        return message


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
    assert plan["interp"] == 13
    assert plan["interp_method"] == "drop"
    assert plan["interp_cic_compensation"] is True
    assert plan["commands"] == [
        "SET auth t=kiwi p=",
        "SET zoom=0 cf=5000.000",
        "SET maxdb=0 mindb=-110",
        "SET wf_speed=1",
        "SET wf_comp=0",
        "SET interp=13",
        "SET keepalive",
    ]


def test_live_waterfall_config_rejects_unsupported_interpolation(tmp_path: Path):
    config = LiveWaterfallCaptureConfig(
        host="10.0.0.40",
        port=8073,
        output=tmp_path / "wf.jsonl",
        interp=5,
    )

    with pytest.raises(LiveCaptureError, match="0..4 or 10..14"):
        config.validate()


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
    frames = []

    path = asyncio.run(
        capture_live_waterfall(
            config,
            allow_live=True,
            websocket_connect=fake_connect,
            status_callback=metrics.append,
            frame_callback=frames.append,
        )
    )

    events = load_jsonl_events(path)
    raw_events = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
    assert path == output
    assert fake_connect.calls[0][0] == "ws://10.0.0.40:8073/123456/W/F"
    assert fake_connect.calls[0][1]["ping_interval"] is None
    assert fake_connect.websocket.sent == config.dry_run_plan()["commands"]
    assert raw_events[0]["dir"] == "meta"
    assert raw_events[0]["stream"] == "wf"
    assert [event.raw["text"] for event in events if event.dir == "tx"] == config.dry_run_plan()["commands"]
    assert [event.binary_payload for event in events if event.type == "binary"] == [WF_PAYLOAD]
    assert metrics[-1]["wf_seq"] == 42
    assert metrics[-1]["wf_frames"] == 1
    assert metrics[-1]["ascii_row"] == "   +@"
    assert len(frames) == 1
    assert frames[0].sequence == 42
    assert frames[0].dbm == (-255, -200, -127, -55, 0)


def test_capture_live_waterfall_sends_queued_navigation_command(tmp_path: Path):
    config = LiveWaterfallCaptureConfig(
        host="10.0.0.40",
        port=8073,
        output=tmp_path / "wf-control.jsonl",
        timestamp=123456,
        max_frames=1,
    )
    fake_connect = FakeConnect([WF_PAYLOAD])
    commands: queue.Queue[str] = queue.Queue()
    commands.put("SET zoom=8 cf=5000.1250")

    asyncio.run(
        capture_live_waterfall(
            config,
            allow_live=True,
            websocket_connect=fake_connect,
            command_queue=commands,
        )
    )

    assert fake_connect.websocket.sent[-1] == "SET zoom=8 cf=5000.1250"


def test_capture_live_waterfall_reports_websocket_closure_without_raw_transport_error(tmp_path: Path):
    output = tmp_path / "wf.jsonl"
    config = LiveWaterfallCaptureConfig(
        host="10.0.0.40",
        port=8073,
        output=output,
        timestamp=123456,
        duration_seconds=0,
        max_frames=0,
    )
    fake_connect = FakeConnect([ConnectionClosedError(None, None)])

    with pytest.raises(LiveCaptureError, match="waterfall WebSocket closed: no close frame"):
        asyncio.run(
            capture_live_waterfall(
                config,
                allow_live=True,
                websocket_connect=fake_connect,
            )
        )


def test_capture_live_waterfall_contextualizes_frequency_from_msg_metadata(tmp_path: Path):
    output = tmp_path / "wf.jsonl"
    max_bins = 1024 << 14
    payload = (
        b"W/F\x00"
        + (max_bins // 4).to_bytes(4, "little")
        + (0x00010002).to_bytes(4, "little")
        + (1).to_bytes(4, "little")
        + bytes([100]) * 1024
    )
    config = LiveWaterfallCaptureConfig(
        host="10.0.0.40",
        port=8073,
        output=output,
        timestamp=123456,
        max_frames=1,
    )
    fake_connect = FakeConnect([
        b"MSG bandwidth=30000000 wf_fft_size=1024 zoom_max=14",
        payload,
    ])
    frames = []
    metrics = []

    asyncio.run(
        capture_live_waterfall(
            config,
            allow_live=True,
            websocket_connect=fake_connect,
            frame_callback=frames.append,
            status_callback=metrics.append,
        )
    )

    assert frames[0].start_khz == pytest.approx(7500.0)
    assert frames[0].center_khz == pytest.approx(11250.0)
    assert frames[0].span_khz == pytest.approx(7500.0)
    assert metrics[0]["bin_width_hz"] == pytest.approx(7500_000 / 1024)


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
