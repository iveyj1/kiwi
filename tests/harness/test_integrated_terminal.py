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
    format_frequency_tick_ruler,
    format_preset_ruler,
    main,
    nearest_step_pair_index,
    format_rssi_indicator,
    rssi_s_unit,
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
    assert layout.divider_row == 20
    assert layout.tui_top == 21
    assert layout.tui_rows == 19
    assert layout.columns == 120


def test_rssi_indicator_formats_hf_s_units_and_bounded_bar():
    assert rssi_s_unit(-121) == "S1"
    assert rssi_s_unit(-73) == "S9"
    assert rssi_s_unit(-53) == "S9+20"
    assert rssi_s_unit(-20) == "S9+53"

    weak = format_rssi_indicator(-120.0, width=10)
    strong = format_rssi_indicator(-40.0, width=10)
    assert weak == "RSSI -120.0 dBm S1    [#---------]"
    assert strong == "RSSI  -40.0 dBm S9+33 [########--]"
    assert len(weak) == len(strong)
    assert format_rssi_indicator(None, width=10) == "RSSI ------ dBm ----- [----------]"


def test_console_default_step_selects_matching_configured_pair():
    pairs = ((100, 10), (1000, 100), (5000, 1000))
    assert nearest_step_pair_index(pairs, main_hz=1000, small_hz=100) == 1
    assert nearest_step_pair_index(pairs, main_hz=1100, small_hz=90) == 1


def test_integrated_layout_rejects_terminal_too_small():
    with pytest.raises(ValueError, match="at least"):
        IntegratedTerminalLayout.compute(columns=30, lines=8)


def test_console_frequency_entry_tunes_without_implicit_recenter():
    model = __import__("kiwi_client.gui_app", fromlist=["WaterfallGuiModel"]).WaterfallGuiModel(history_rows=5)
    timeline = __import__("kiwi_client.gui_app", fromlist=["FixtureWaterfallTimeline"]).FixtureWaterfallTimeline.from_fixture(FIXTURE)
    timeline.advance(model.publisher)
    model.display_frequency_range()
    original_center = model.session.state.waterfall_center_khz

    model.set_tuned_frequency(860.0)

    assert model.session.state.frequency_khz == pytest.approx(860.0)
    assert model.session.state.selected_khz == pytest.approx(860.0)
    assert model.session.state.waterfall_center_khz == pytest.approx(original_center)


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
    assert ruler[round((760.0 - 737.0) / (972.0 - 737.0) * 79)] == "|"
    assert "x 5000.000" not in ruler


def test_frequency_tick_ruler_aligns_bars_omits_units_and_skips_uneven_edge():
    marks, labels = format_frequency_tick_ruler(260.0, 308.6, columns=81)

    assert len(marks) == len(labels) == 81
    assert marks[0] == "|"  # aligned 260 major survives at the edge
    assert "280" in labels
    assert "300" in labels
    assert "308.6" not in labels
    assert "kHz" not in labels


def test_kitty_pane_presenter_uses_absolute_saved_cursor_and_deletes_image():
    output = io.BytesIO()
    presenter = KittyPanePresenter(output=output, force=True, environ={})
    layout = IntegratedTerminalLayout.compute(columns=80, lines=24)
    image = RasterImage(width=2, height=1, rgb=bytes((0, 0, 0, 255, 255, 255)))

    presenter.draw(image, layout)
    presenter.clear()
    presenter.finish()
    payload = output.getvalue()

    assert b"\x1b7\x1b[1;1H" in payload
    assert b"c=80" in payload
    assert f"r={layout.waterfall_rows}".encode() in payload
    assert b"\x1b8" in payload
    assert payload.count(b"a=d,d=i,i=41,q=2") == 1


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

    previous_publisher = model.publisher
    _response, switch_message = controller.switch_receiver(
        "10.0.0.41:8073",
        preserve_playback=True,
        join_timeout=1,
        startup_grace_seconds=0.01,
    )
    assert "restarted" in switch_message
    assert controller.waterfall_snapshots is not previous_publisher
    assert source.poll_generation() == -1
    deadline = time.monotonic() + 1
    while source.poll_generation() == 0 and time.monotonic() < deadline:
        time.sleep(0.01)
    assert model.publisher.latest().generation == 1

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


def test_controller_console_source_rebinds_replacement_publisher_after_receiver_switch():
    class Controller:
        def __init__(self):
            self.commands = []
            self.waterfall_snapshots = WaterfallSnapshotPublisher(max_rows=4)
            self.paired_session = RadioSessionManager()

        def execute(self, command):
            self.commands.append(command)
            return {}

        def dispatch_session_action(self, action):
            return self.paired_session.dispatch(action)

    controller = Controller()
    model = __import__("kiwi_client.gui_app", fromlist=["WaterfallGuiModel"]).WaterfallGuiModel(history_rows=4)
    source = ControllerConsoleSource(controller, model=model)
    source.start()
    old_rasterizer = model.rasterizer

    replacement = WaterfallSnapshotPublisher(max_rows=4)
    controller.waterfall_snapshots = replacement
    assert source.poll_generation() == -1

    assert model.publisher is replacement
    assert model.rasterizer is not old_rasterizer
    replacement.append(WaterfallFrame(sequence=2, bins=(0, 0), dbm=(-90, -80), start_khz=100, span_khz=20))
    assert source.poll_generation() == 1
    source.stop()


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
    assert result["steps_khz"] == [1.0, 0.1]
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
    assert result["steps_khz"] == [1.0, 0.1]
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
