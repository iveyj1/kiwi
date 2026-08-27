"""Guardrail, CLI, and live-loop tests for the W/F offset sweep.

The live path runs against a fake websocket that synthesises W/F frames for
whatever window it is tuned to, so no receiver is involved.
"""

import asyncio
import json
from pathlib import Path

import pytest

from kiwi_client.live_capture import LiveCaptureError
from kiwi_client.waterfall import WaterfallSpan
from kiwi_client.waterfall_sweep import (
    WaterfallSweepConfig,
    load_sweep_fixture,
    main,
    sweep_waterfall_window,
)

REFERENCE_KHZ = 60.0
TRUE_OFFSET = 0.83


def _wf_payload(x_bin_server: int, peak_bin: int) -> bytes:
    """Build a W/F frame carrying a single carrier at `peak_bin`."""
    body = (
        x_bin_server.to_bytes(4, "little")
        + (9).to_bytes(4, "little")
        + (0).to_bytes(4, "little")
    )
    bins = bytes(255 - 90 if i != peak_bin else 255 - 30 for i in range(1024))
    return b"W/F\x20" + body + bins


class SweepingWebSocket:
    """Fake receiver that tracks `SET zoom/cf` and emits frames for that window."""

    def __init__(self, span: WaterfallSpan, true_offset: float):
        self.span = span
        self.true_offset = true_offset
        self.sent: list[str] = []
        self.x_bin_server: int | None = None
        self.setup_msgs_pending = True

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def send(self, command: str) -> None:
        self.sent.append(command)
        if command.startswith("SET zoom="):
            cf_khz = float(command.split("cf=")[1])
            start_hz = cf_khz * 1000 - self.span.span_hz / 2
            self.x_bin_server = round(start_hz / self.span.unit_hz)
            self.setup_msgs_pending = True

    async def recv(self):
        if self.setup_msgs_pending:
            self.setup_msgs_pending = False
            return (
                "MSG center_freq=15000000 bandwidth=30000000 "
                "wf_fft_size=1024 zoom_max=14 "
                f"zoom={self.span.zoom} start={self.x_bin_server}"
            )
        naive = (REFERENCE_KHZ * 1000 - self.span.start_hz(self.x_bin_server)) / self.span.bin_width_hz
        return _wf_payload(self.x_bin_server, round(naive - self.true_offset))


class SweepingConnect:
    def __init__(self, span: WaterfallSpan, true_offset: float = TRUE_OFFSET):
        self.websocket = SweepingWebSocket(span, true_offset)
        self.calls: list[tuple] = []

    def __call__(self, uri, **kwargs):
        self.calls.append((uri, kwargs))
        return self.websocket


def _config(tmp_path: Path, **overrides) -> WaterfallSweepConfig:
    defaults = dict(
        host="10.0.0.40",
        port=8073,
        output=tmp_path / "sweep.jsonl",
        reference_khz=REFERENCE_KHZ,
        zoom=9,
        steps=40,
        step_hz=2.0,
        frames_per_step=3,
        timestamp=123456,
    )
    defaults.update(overrides)
    return WaterfallSweepConfig(**defaults)


def test_sweep_rejects_disallowed_receiver(tmp_path: Path):
    with pytest.raises(LiveCaptureError, match="allowed receivers"):
        _config(tmp_path, host="8.8.8.8").validate()


def test_sweep_rejects_zoom_that_cannot_center_the_reference(tmp_path: Path):
    with pytest.raises(LiveCaptureError, match="cannot be centred"):
        _config(tmp_path, zoom=5).validate()


def test_sweep_rejects_a_sweep_too_short_to_cross_a_bin(tmp_path: Path):
    with pytest.raises(LiveCaptureError, match="never cross a bin boundary"):
        _config(tmp_path, steps=5).validate()


def test_sweep_rejects_a_step_too_coarse_to_improve_on_existing_bound(tmp_path: Path):
    with pytest.raises(LiveCaptureError, match="too coarse"):
        _config(tmp_path, step_hz=20.0).validate()


def test_sweep_requires_allow_live(tmp_path: Path):
    with pytest.raises(LiveCaptureError, match="requires allow_live"):
        asyncio.run(sweep_waterfall_window(_config(tmp_path), allow_live=False))


def test_sweep_refuses_to_overwrite_without_the_flag(tmp_path: Path):
    output = tmp_path / "sweep.jsonl"
    output.write_text("")
    with pytest.raises(LiveCaptureError, match="already exists"):
        _config(tmp_path, output=output).validate()


def test_dry_run_plan_reports_geometry_without_connecting(tmp_path: Path):
    plan = _config(tmp_path).dry_run_plan()

    assert plan["websocket_uri"] == "ws://10.0.0.40:8073/123456/W/F"
    assert plan["positions_per_bin"] == 32.0
    assert plan["sweep_width_bins"] > 1.0, "the planned sweep must cross a bin boundary"
    assert plan["step_bins"] < 0.1
    assert plan["commands_first_step"][0] == "SET auth t=kiwi p="


def test_live_sweep_recovers_the_planted_offset_with_a_fake_websocket(tmp_path: Path):
    span = WaterfallSpan(bandwidth_hz=30_000_000.0, zoom=9)
    config = _config(tmp_path)
    connect = SweepingConnect(span)

    path = asyncio.run(sweep_waterfall_window(config, allow_live=True, websocket_connect=connect))

    result = load_sweep_fixture(path, reference_khz=REFERENCE_KHZ)
    low, high = result.offset_window()
    assert low < TRUE_OFFSET <= high
    assert high - low < 0.05
    assert result.crossed_bin_boundary()


def test_live_sweep_retunes_once_per_step(tmp_path: Path):
    span = WaterfallSpan(bandwidth_hz=30_000_000.0, zoom=9)
    config = _config(tmp_path, steps=40)
    connect = SweepingConnect(span)

    asyncio.run(sweep_waterfall_window(config, allow_live=True, websocket_connect=connect))

    tunes = [c for c in connect.websocket.sent if c.startswith("SET zoom=")]
    assert len(tunes) == 40
    assert connect.websocket.sent[0] == "SET auth t=kiwi p="


def test_live_sweep_reports_progress_per_step(tmp_path: Path):
    span = WaterfallSpan(bandwidth_hz=30_000_000.0, zoom=9)
    updates: list[dict] = []

    asyncio.run(
        sweep_waterfall_window(
            _config(tmp_path),
            allow_live=True,
            websocket_connect=SweepingConnect(span),
            status_callback=updates.append,
        )
    )

    assert len(updates) == 40
    assert updates[-1]["step"] == 40


def test_live_sweep_surfaces_a_busy_receiver(tmp_path: Path):
    span = WaterfallSpan(bandwidth_hz=30_000_000.0, zoom=9)
    connect = SweepingConnect(span)

    async def busy():
        return "MSG too_busy=8"

    connect.websocket.recv = busy

    with pytest.raises(LiveCaptureError, match="busy"):
        asyncio.run(sweep_waterfall_window(_config(tmp_path), allow_live=True, websocket_connect=connect))


def test_cli_dry_run_prints_a_plan(capsys, tmp_path: Path):
    code = main([
        "--dry-run", "--output", str(tmp_path / "s.jsonl"),
        "--reference-khz", "60", "--zoom", "9", "--timestamp", "123456",
    ])

    payload = json.loads(capsys.readouterr().out)
    assert code == 0
    assert payload["reference_khz"] == 60.0
    assert payload["sweep_width_bins"] > 1.0


def test_cli_requires_allow_live(tmp_path: Path):
    with pytest.raises(SystemExit):
        main(["--output", str(tmp_path / "s.jsonl"), "--reference-khz", "60"])


def test_cli_requires_output_for_a_live_sweep():
    with pytest.raises(SystemExit):
        main(["--allow-live", "--reference-khz", "60"])


def test_cli_analyse_mode_reads_a_fixture_without_network(tmp_path: Path, capsys):
    span = WaterfallSpan(bandwidth_hz=30_000_000.0, zoom=9)
    output = tmp_path / "sweep.jsonl"
    asyncio.run(
        sweep_waterfall_window(
            _config(tmp_path, output=output), allow_live=True, websocket_connect=SweepingConnect(span)
        )
    )
    capsys.readouterr()

    code = main(["--analyse", str(output), "--reference-khz", "60", "--json"])

    payload = json.loads(capsys.readouterr().out)
    assert code == 0
    assert payload["offset_low"] < TRUE_OFFSET <= payload["offset_high"]
    assert payload["crossed_bin_boundary"] is True


def test_cli_analyse_mode_renders_a_readable_report(tmp_path: Path, capsys):
    span = WaterfallSpan(bandwidth_hz=30_000_000.0, zoom=9)
    output = tmp_path / "sweep.jsonl"
    asyncio.run(
        sweep_waterfall_window(
            _config(tmp_path, output=output), allow_live=True, websocket_connect=SweepingConnect(span)
        )
    )
    capsys.readouterr()

    main(["--analyse", str(output), "--reference-khz", "60"])

    out = capsys.readouterr().out
    assert "offset in (" in out
    assert "WARNING" not in out, "a full sweep crossed a boundary and should not warn"
