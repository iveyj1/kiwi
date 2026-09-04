import io
import json
import time
from pathlib import Path

import pytest

from kiwi_client.client_app import ClientController, ClientState
from kiwi_client.integrated_terminal import (
    ControllerConsoleSource,
    IntegratedTerminalLayout,
    KittyPanePresenter,
    format_passband_scale,
    format_preset_ruler,
    main,
)
from kiwi_client.session_manager import RadioSessionManager
from kiwi_client.waterfall import WaterfallFrame
from kiwi_client.waterfall_raster import RasterImage
from kiwi_client.waterfall_snapshots import WaterfallSnapshotPublisher


FIXTURE = Path("tests/fixtures/kiwi/local-wf-am-855-zoom7.jsonl")


def test_integrated_layout_reserves_waterfall_rulers_and_tui_region():
    layout = IntegratedTerminalLayout.compute(columns=120, lines=40)

    assert layout.waterfall_top == 0
    assert layout.waterfall_rows == 20
    assert layout.passband_row == 20
    assert layout.frequency_row == 21
    assert layout.preset_row == 22
    assert layout.tui_top == 24
    assert layout.tui_rows == 16
    assert layout.columns == 120


def test_integrated_layout_rejects_terminal_too_small():
    with pytest.raises(ValueError, match="at least"):
        IntegratedTerminalLayout.compute(columns=30, lines=8)


def test_passband_scale_uses_bracket_center_and_separate_selection_pointer():
    scale = format_passband_scale(
        737.0,
        972.0,
        tuned_khz=760.0,
        selected_khz=800.0,
        low_cut_hz=-5000,
        high_cut_hz=5000,
        columns=80,
    )

    assert len(scale) == 80
    assert "└" in scale and "┴" in scale and "┘" in scale
    assert "▼" in scale
    assert scale.index("▼") > scale.index("┘")


def test_preset_ruler_places_only_visible_non_overlapping_presets():
    ruler = format_preset_ruler(
        {
            "a": {"frequency_khz": 760.0},
            "b": {"frequency_khz": 800.0},
            "x": {"frequency_khz": 5000.0},
        },
        737.0,
        972.0,
        columns=80,
    )

    assert len(ruler) == 80
    assert "a 760.000" in ruler
    assert "b 800.000" in ruler
    assert "x 5000.000" not in ruler


def test_kitty_pane_presenter_uses_absolute_saved_cursor_and_deletes_image():
    output = io.BytesIO()
    presenter = KittyPanePresenter(output=output, force=True, environ={})
    layout = IntegratedTerminalLayout.compute(columns=80, lines=24)
    image = RasterImage(width=2, height=1, rgb=bytes((0, 0, 0, 255, 255, 255)))

    presenter.draw(image, layout)
    presenter.finish()
    payload = output.getvalue()

    assert b"\x1b7\x1b[1;1H" in payload
    assert b"c=80" in payload
    assert f"r={layout.waterfall_rows}".encode() in payload
    assert b"\x1b8" in payload
    assert b"a=d,d=i,i=41,q=2" in payload


def test_controller_console_source_binds_shared_state_starts_and_stops_pair():
    class Controller:
        def __init__(self):
            self.commands = []
            self.waterfall_snapshots = WaterfallSnapshotPublisher(max_rows=12)
            self.paired_session = RadioSessionManager()

        def execute(self, command):
            self.commands.append(command)
            return {"type": "operation-status"}

        def dispatch_session_action(self, action):
            return self.paired_session.dispatch(action)

    controller = Controller()
    model = __import__("kiwi_client.gui_app", fromlist=["WaterfallGuiModel"]).WaterfallGuiModel(history_rows=12)
    source = ControllerConsoleSource(controller, model=model, audio=False)

    source.start()
    assert model.publisher is controller.waterfall_snapshots
    assert model.session is controller.paired_session
    assert model.action_dispatch == controller.dispatch_session_action
    assert controller.commands == ["radio-bg --allow-live --null-sink"]
    assert source.poll_generation() == 0

    source.stop()
    source.stop()
    assert controller.commands == [
        "radio-bg --allow-live --null-sink",
        "stop",
        "wait 5",
    ]


def test_controller_console_source_with_fake_operations_publishes_and_routes_cleanup():
    class Operations:
        def __init__(self):
            self.routed = []

        def paired(self, waterfall_config, snd_config, *, null_sink, stop_event, command_queue, status_callback, frame_callback=None):
            status_callback({"snd_status": "running", "wf_status": "running"})
            frame_callback(WaterfallFrame(sequence=1, bins=(0, 0), dbm=(-90, -80), start_khz=100.0, span_khz=20.0))
            while not stop_event.is_set():
                try:
                    self.routed.append(command_queue.get(timeout=0.01))
                except Exception:
                    pass
            while not command_queue.empty():
                self.routed.append(command_queue.get_nowait())
            return {"stopped": True}

    operations = Operations()
    controller = ClientController(
        state=ClientState(host="10.0.0.40", frequency_khz=110.0, duration_seconds=0, max_frames=0),
        operations=operations,
    )
    controller.configure_waterfall_session(center_khz=110.0, zoom=0, speed=1, interp=13, history_rows=4)
    model = __import__("kiwi_client.gui_app", fromlist=["WaterfallGuiModel"]).WaterfallGuiModel(
        history_rows=4,
        tuned_khz=110.0,
        show_frequency_lines=False,
    )
    source = ControllerConsoleSource(controller, model=model, audio=False)

    source.start()
    deadline = time.monotonic() + 1
    while source.poll_generation() == 0 and time.monotonic() < deadline:
        time.sleep(0.01)
    assert model.publisher.latest().generation == 1
    assert model.image().width == 2

    model.move_selection(1)
    model.tune_selected()
    source.stop()

    streams = [getattr(item, "stream", None) for item in operations.routed]
    assert "snd" in streams
    assert controller.background.status().running is False


def test_controller_console_source_exposes_failed_background_without_hanging_cleanup():
    class Operations:
        def paired(self, *args, **kwargs):
            raise RuntimeError("synthetic W/F failure")

    controller = ClientController(
        state=ClientState(host="10.0.0.40", duration_seconds=0, max_frames=0),
        operations=Operations(),
    )
    controller.configure_waterfall_session(center_khz=5000, zoom=0, speed=1, interp=13, history_rows=4)
    model = __import__("kiwi_client.gui_app", fromlist=["WaterfallGuiModel"]).WaterfallGuiModel(history_rows=4)
    source = ControllerConsoleSource(controller, model=model)

    source.start()
    deadline = time.monotonic() + 1
    while controller.background.status().running and time.monotonic() < deadline:
        time.sleep(0.01)
    source.stop()

    assert "synthetic W/F failure" in controller.background.status().error


def test_controller_console_source_audio_mode_omits_null_sink():
    class Controller:
        waterfall_snapshots = WaterfallSnapshotPublisher(max_rows=4)
        paired_session = RadioSessionManager()

        def __init__(self):
            self.commands = []

        def execute(self, command):
            self.commands.append(command)
            return {}

        def dispatch_session_action(self, action):
            return self.paired_session.dispatch(action)

    controller = Controller()
    model = __import__("kiwi_client.gui_app", fromlist=["WaterfallGuiModel"]).WaterfallGuiModel(history_rows=4)
    source = ControllerConsoleSource(controller, model=model, audio=True)
    source.start()
    source.stop()

    assert controller.commands[0] == "radio-bg --allow-live"


def test_integrated_live_dry_run_requires_flag_but_does_not_connect(capsys):
    code = main([
        "--allow-live", "--receiver", "10.0.0.40:8073",
        "--config", "config.toml", "--dry-run",
    ])

    assert code == 0
    result = json.loads(capsys.readouterr().out)
    assert result["network"] is False
    assert result["receiver"] == "10.0.0.40:8073"
    assert result["would_start"] == "radio-bg --allow-live --null-sink"


def test_integrated_fixture_dry_run_has_no_network_or_terminal_dependency(capsys):
    code = main([
        "--fixture", str(FIXTURE),
        "--presets", "presets.toml",
        "--repeat", "2",
        "--dry-run",
    ])

    assert code == 0
    result = json.loads(capsys.readouterr().out)
    assert result["backend"] == "kitty+curses"
    assert result["fixture_frames"] == 10
    assert result["network"] is False
    assert "a 760.000" in result["presets_visible"]


def test_kitty_pane_presenter_coalesces_identical_generation():
    output = io.BytesIO()
    presenter = KittyPanePresenter(output=output, force=True, environ={})
    layout = IntegratedTerminalLayout.compute(columns=80, lines=24)
    image = RasterImage(width=1, height=1, rgb=b"\x00\x00\x00")

    assert presenter.draw(image, layout, generation=3) is True
    size = len(output.getvalue())
    assert presenter.draw(image, layout, generation=3) is False
    assert len(output.getvalue()) == size
    assert presenter.draw(image, layout, generation=4) is True
