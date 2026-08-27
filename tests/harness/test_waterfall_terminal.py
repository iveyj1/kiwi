import asyncio
import base64
import io
import os
import threading
from pathlib import Path

import pytest

from kiwi_client.live_waterfall import LiveWaterfallCaptureConfig
from kiwi_client.waterfall import WaterfallFrame
from kiwi_client.waterfall_raster import PASSBAND_MARKER_RGB, TUNED_MARKER_RGB, RasterImage
from kiwi_client.waterfall_terminal import (
    KittyTerminalBackend,
    WaterfallTerminalViewer,
    _viewer,
    apply_waterfall_config,
    build_arg_parser,
    choose_frequency_tick_step,
    default_terminal_placement,
    encode_kitty_image,
    format_frequency_ruler,
    frequency_label_decimals,
    frequency_ticks,
    preview_terminal_fixture,
    terminal_supports_kitty,
    view_live_waterfall,
)
from kiwi_client.config import default_config, load_config
from tests.harness.test_live_waterfall import FakeConnect, WF_PAYLOAD

FIXTURE = Path("tests/fixtures/kiwi/local-wf-5000-zoom0.jsonl")


class FakeBackend:
    def __init__(self):
        self.images = []
        self.frequency_ranges = []
        self.draw_threads = []

    def set_frequency_range(self, start_khz, end_khz):
        self.frequency_ranges.append((start_khz, end_khz))

    def draw(self, image):
        self.draw_threads.append(threading.get_ident())
        self.images.append(image)


def _encoded_payload(message: bytes) -> bytes:
    chunks = []
    for sequence in message.split(b"\x1b_G")[1:]:
        body = sequence.removesuffix(b"\x1b\\")
        _controls, payload = body.split(b";", 1)
        chunks.append(payload)
    return base64.b64decode(b"".join(chunks))


def test_kitty_encoder_chunks_png_and_reuses_requested_placement():
    png = b"a deterministic fake png payload"

    message = encode_kitty_image(png, image_id=7, columns=80, rows=20, chunk_size=12)

    assert message.count(b"\x1b_G") == 4
    assert b"a=T,f=100,t=d,i=7,p=1,q=2,C=1,c=80,r=20,m=1" in message
    assert b"m=0;" in message
    assert _encoded_payload(message) == png


def test_default_terminal_placement_uses_full_width_and_half_height():
    assert default_terminal_placement(columns=120, lines=40) == (120, 20)
    assert default_terminal_placement(columns=1, lines=1) == (1, 1)


def test_waterfall_config_applies_defaults_but_cli_overrides(tmp_path: Path):
    path = tmp_path / "config.toml"
    path.write_text(
        """
[waterfall]
center_khz = 855
zoom = 7
history_rows = 300
terminal_rows = 30
render_min_db = -105
render_max_db = -35
speed = 4
refresh_hz = 12
interp = 13
label_columns_per_tick = 20
show_tuned_marker = true
show_passband = true
low_cut_hz = -5000
high_cut_hz = 5000
""".strip(),
        encoding="utf-8",
    )
    parser = build_arg_parser()
    configured = apply_waterfall_config(parser.parse_args(["--config", str(path)]), load_config(path))
    overridden = apply_waterfall_config(
        parser.parse_args(["--config", str(path), "--rows", "77", "--speed", "2", "--no-show-passband"]),
        load_config(path),
    )

    assert configured.center_khz == 855.0
    assert configured.zoom == 7
    assert configured.rows == 300
    assert configured.terminal_rows == 30
    assert configured.label_columns_per_tick == 20
    assert configured.show_passband is True
    assert configured.low_cut_hz == -5000
    assert configured.duration_seconds == 60.0
    assert configured.max_frames == 1500
    assert overridden.rows == 77
    assert overridden.speed == 2
    assert overridden.show_passband is False


def test_viewer_defaults_to_current_terminal_placement(monkeypatch):
    monkeypatch.setattr("kiwi_client.waterfall_terminal.shutil.get_terminal_size", lambda fallback=None: os.terminal_size((132, 48)))
    args = apply_waterfall_config(
        build_arg_parser().parse_args(["--fixture", str(FIXTURE)]),
        default_config(),
    )

    viewer = _viewer(args, io.BytesIO())

    assert viewer.backend.columns == 132
    assert viewer.backend.rows == 24


def test_terminal_capability_detection_is_explicit_and_conservative():
    assert terminal_supports_kitty({"KITTY_WINDOW_ID": "12", "TERM": "xterm"}) is True
    assert terminal_supports_kitty({"TERM": "xterm-kitty"}) is True
    assert terminal_supports_kitty({"TERM_PROGRAM": "ghostty", "TERM": "xterm-256color"}) is True
    assert terminal_supports_kitty({"TERM": "xterm-256color"}) is False


def test_kitty_backend_refuses_unknown_terminal_unless_forced():
    output = io.BytesIO()
    image = RasterImage(width=1, height=1, rgb=b"\x00\x00\x00")

    with pytest.raises(RuntimeError, match="Kitty graphics"):
        KittyTerminalBackend(output=output, environ={}).draw(image)

    KittyTerminalBackend(output=output, environ={}, force=True).draw(image)
    assert output.getvalue().startswith(b"\x1b_G")


@pytest.mark.parametrize(
    ("raw_step", "expected"),
    [(0.006, 0.01), (0.3, 0.5), (3.0, 5.0), (38.0, 50.0), (501.0, 1000.0)],
)
def test_frequency_tick_step_uses_1_2_5_policy(raw_step, expected):
    assert choose_frequency_tick_step(raw_step) == pytest.approx(expected)


def test_frequency_label_precision_follows_tick_interval():
    assert frequency_label_decimals(50.0) == 0
    assert frequency_label_decimals(0.5) == 1
    assert frequency_label_decimals(0.01) == 2


def test_frequency_ticks_adapt_to_am_band_and_preserve_edges():
    ticks = frequency_ticks(760.0, 950.0, columns=120)

    assert [tick.frequency_khz for tick in ticks] == [760.0, 800.0, 850.0, 900.0, 950.0]
    assert ticks[0].label_start == 0
    assert ticks[-1].label_stop == 120
    assert all(left.label_stop <= right.label_start for left, right in zip(ticks, ticks[1:]))


def test_frequency_ruler_medium_width_adds_non_overlapping_major_label():
    ticks = frequency_ticks(0.0, 30000.0, columns=60)

    assert [tick.frequency_khz for tick in ticks] == [0.0, 20000.0, 30000.0]
    assert all(left.label_stop <= right.label_start for left, right in zip(ticks, ticks[1:]))


def test_frequency_ruler_narrow_width_keeps_non_overlapping_edges_only():
    ticks = frequency_ticks(0.0, 30000.0, columns=30)
    ruler = format_frequency_ruler(0.0, 30000.0, columns=30)

    assert [tick.frequency_khz for tick in ticks] == [0.0, 30000.0]
    assert len(ruler) == 30
    assert ruler.startswith("0 kHz")
    assert ruler.endswith("30000 kHz")


def test_frequency_ruler_uses_more_precision_for_narrowband_span():
    ticks = frequency_ticks(59.985, 60.015, columns=100)
    ruler = format_frequency_ruler(59.985, 60.015, columns=100)

    assert any(tick.label == "60.00 kHz" for tick in ticks)
    assert ruler.startswith("59.985 kHz")
    assert ruler.endswith("60.015 kHz")
    assert all(left.label_stop <= right.label_start for left, right in zip(ticks, ticks[1:]))


def test_kitty_backend_places_frequency_ruler_above_reserved_image():
    output = io.BytesIO()
    image = RasterImage(width=1, height=1, rgb=b"\x00\x00\x00")
    backend = KittyTerminalBackend(output=output, environ={}, force=True, columns=60, rows=3)

    backend.set_frequency_range(0.0, 30000.0)
    backend.draw(image)

    message = output.getvalue()
    ruler = format_frequency_ruler(0.0, 30000.0, columns=60).encode("ascii")
    assert message.startswith(b"\r\x1b[2K" + ruler + b"\n\n\n\n\x1b[3A\r\x1b_G")


def test_kitty_backend_reserves_visible_area_once_and_restores_cursor():
    output = io.BytesIO()
    image = RasterImage(width=1, height=1, rgb=b"\x00\x00\x00")
    backend = KittyTerminalBackend(output=output, environ={}, force=True, columns=10, rows=3)

    backend.draw(image)
    first_length = len(output.getvalue())
    backend.draw(image)
    backend.finish()

    message = output.getvalue()
    assert message.startswith(b"\n\n\n\x1b[3A\r\x1b_G")
    assert message[:first_length].count(b"\x1b_G") == 1
    assert message[first_length:].startswith(b"\x1b_G")
    assert message.count(b"\n\n\n\x1b[3A\r") == 1
    assert message.endswith(b"\x1b[3B\r")


def test_fixture_preview_builds_full_height_raster_and_draws_once():
    backend = FakeBackend()
    viewer = WaterfallTerminalViewer(backend=backend, max_rows=4, min_dbm=-110, max_dbm=0)

    frames = preview_terminal_fixture(FIXTURE, viewer)

    assert frames == 2
    assert len(backend.images) == 1
    image = backend.images[0]
    assert image.width == 1024
    assert image.height == 4
    assert len(image.rgb) == 1024 * 4 * 3
    assert backend.frequency_ranges == [(0.0, 30000.0)]


def test_live_viewer_uses_guarded_capture_and_parsed_frame_callback(tmp_path: Path):
    backend = FakeBackend()
    viewer = WaterfallTerminalViewer(backend=backend, max_rows=3, min_dbm=-255, max_dbm=0)
    config = LiveWaterfallCaptureConfig(
        host="10.0.0.40",
        port=8073,
        output=tmp_path / "wf.jsonl",
        timestamp=123456,
        max_frames=1,
    )

    path = asyncio.run(
        view_live_waterfall(
            config,
            viewer,
            allow_live=True,
            websocket_connect=FakeConnect([WF_PAYLOAD]),
        )
    )

    assert path.exists()
    assert viewer.history.width == 5
    assert viewer.history.rows() == ((-255, -200, -127, -55, 0),)
    assert backend.images[-1].height == 3


def test_live_viewer_coalesces_immediate_frames_and_draws_off_event_loop(tmp_path: Path):
    backend = FakeBackend()
    viewer = WaterfallTerminalViewer(
        backend=backend,
        max_rows=25,
        min_dbm=-255,
        max_dbm=0,
        refresh_hz=12,
    )
    config = LiveWaterfallCaptureConfig(
        host="10.0.0.40",
        port=8073,
        output=tmp_path / "wf-many.jsonl",
        timestamp=123456,
        duration_seconds=0,
        max_frames=25,
    )
    event_loop_thread = threading.get_ident()

    asyncio.run(
        view_live_waterfall(
            config,
            viewer,
            allow_live=True,
            websocket_connect=FakeConnect([WF_PAYLOAD] * 25),
        )
    )

    assert len(viewer.history) == 25
    assert len(backend.images) == 1
    assert backend.draw_threads == [backend.draw_threads[0]]
    assert backend.draw_threads[0] != event_loop_thread


def test_viewer_raster_applies_configured_tuned_and_passband_overlays():
    viewer = WaterfallTerminalViewer(
        backend=FakeBackend(),
        max_rows=1,
        min_dbm=-100,
        max_dbm=0,
        tuned_khz=150.0,
        low_cut_hz=-25_000,
        high_cut_hz=25_000,
        show_tuned_marker=True,
        show_passband=True,
    )
    frame = WaterfallFrame(
        sequence=1,
        bins=(155,) * 5,
        dbm=(-100,) * 5,
        start_khz=100.0,
        span_khz=100.0,
    )

    viewer.append(frame, draw=False)
    image = viewer.raster()
    pixels = [tuple(image.rgb[column * 3:(column + 1) * 3]) for column in range(5)]

    assert pixels[1] == PASSBAND_MARKER_RGB
    assert pixels[2] == TUNED_MARKER_RGB
    assert pixels[3] == PASSBAND_MARKER_RGB


def test_viewer_rejects_invalid_render_range():
    with pytest.raises(ValueError, match="greater"):
        WaterfallTerminalViewer(backend=FakeBackend(), max_rows=4, min_dbm=0, max_dbm=0)
