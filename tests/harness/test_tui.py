from pathlib import Path

import curses
import json
import time

from kiwi_client.client_app import ClientController, ClientState
from kiwi_client.config import load_config
from kiwi_client.tui import (
    InputMode,
    TuiInputState,
    expand_key_action,
    handle_tui_key,
    normalize_key_name,
    render_command_hints,
    render_dashboard,
    render_keymap_hints,
    render_tui_hints,
    request_tui_quit,
    run_tui,
    start_startup_playback,
    startup_receiver_presets,
    startup_state_and_presets,
    state_from_config,
)


def test_render_keymap_hints_show_requested_grouped_help():
    text = render_keymap_hints(load_config())

    assert "Key hints" in text
    assert ": — command mode" in text
    assert "Tuning" in text
    assert "h — tune down" in text
    assert "l — tune up" in text
    assert "Tuning modifiers" in text
    assert "<shift> h/l — small step" in text
    assert "<ctrl> h/l — large step" in text
    assert "Volume" in text
    assert "k — volume up" in text
    assert "j — volume down" in text
    assert "Presets" in text
    assert "p <register> — recall preset" in text
    assert "s <register> — store preset (frequency, mode and bandwidth only)" in text
    assert "S <register> — store preset (all radio parameters)" in text
    assert "<register> is [0..9] or [a..z]" in text
    assert "r <receiver> — switch to specified receiver" in text
    assert "<receiver> is [0..9] or [a..z] from list of receivers" in text
    assert "Radio parameters are transferred to new receiver" in text
    assert "q — quit" in text
    assert len(text.splitlines()) <= 15


def test_render_command_hints_show_grouped_top_level_shortcuts_and_descriptions():
    text = render_command_hints("")

    assert "Command hints" in text
    assert "Status" in text
    assert "Connection" in text
    assert "Tuning" in text
    assert "Playback" in text
    assert "Recording/capture" in text
    assert "    tu (tune) — set frequency" in text
    assert "    mo (mode) — set demod mode" in text
    assert "    pb (play-bg) — start playback worker" in text
    assert len(text.splitlines()) <= 25


def test_render_command_hints_filter_by_typed_prefix():
    text = render_command_hints("mo")

    assert "mo (mode) — set demod mode" in text
    assert "args: mode <mode> [low_cut_hz high_cut_hz]" in text
    assert "tu (tune)" not in text


def test_render_command_hints_show_unique_command_arguments():
    text = render_command_hints("agc g")

    assert "ag (agc) — AGC settings" in text
    assert "sub-options: on, off, hang on|off, threshold <value>, slope <value>, decay <ms>, gain <value>, set key=value ..." in text


def test_render_command_hints_use_current_semicolon_segment():
    text = render_command_hints("tu 7000; mo")

    assert "active: mo" in text
    assert "mo (mode) — set demod mode" in text
    assert "tu (tune)" not in text


def test_render_tui_hints_switches_by_input_mode():
    assert "Key hints" in render_tui_hints(TuiInputState(mode=InputMode.KEYMAP), load_config())
    assert "Command hints" in render_tui_hints(TuiInputState(mode=InputMode.COMMAND, command="tu"), load_config())


def test_render_tui_hints_show_pending_prefix_context():
    assert "Recall preset" in render_tui_hints(TuiInputState(pending_key_action="recall-preset"), load_config())
    assert "Receiver" in render_tui_hints(TuiInputState(pending_key_action="receiver"), load_config())


def test_render_tui_hints_show_defined_preset_register_frequency_and_mode():
    controller = ClientController(volume_control=TuiFakeVolumeControl())
    controller.execute("tune 7100")
    controller.execute("mode usb 300 2700")
    controller.execute("store a")

    text = render_tui_hints(TuiInputState(pending_key_action="recall-preset"), load_config(), controller)

    assert "a — 7100.000 kHz usb" in text
    assert "b —" not in text


def test_render_tui_hints_show_stored_receiver_register_descriptions(tmp_path):
    controller = ClientController()
    controller.execute("add-receiver a 10.0.0.42:8073 Backup receiver")

    text = render_tui_hints(TuiInputState(pending_key_action="receiver"), load_config(), controller)

    assert "a — 10.0.0.42:8073 Backup receiver" in text


def test_render_tui_hints_show_receiver_registers_sorted_by_register(tmp_path):
    config_path = tmp_path / "config.toml"
    config_path.write_text(
        """
[receivers]
allowed = ["10.0.0.41:8073", "10.0.0.40:8073"]
""".strip(),
        encoding="utf-8",
    )
    controller = ClientController()
    controller.execute("add-receiver 2 10.0.0.42:8073 Backup receiver")

    text = render_tui_hints(TuiInputState(pending_key_action="receiver"), load_config(config_path), controller)

    assert text.index("0 — 10.0.0.41:8073") < text.index("1 — 10.0.0.40:8073")
    assert text.index("1 — 10.0.0.40:8073") < text.index("2 — 10.0.0.42:8073 Backup receiver")


def test_render_tui_hints_show_receiver_register_addresses(tmp_path):
    config_path = tmp_path / "config.toml"
    config_path.write_text(
        """
[receivers]
allowed = ["10.0.0.41:8073", "10.0.0.40:8073"]
""".strip(),
        encoding="utf-8",
    )

    text = render_tui_hints(TuiInputState(pending_key_action="receiver"), load_config(config_path), ClientController())

    assert "0 — 10.0.0.41:8073" in text
    assert "1 — 10.0.0.40:8073" in text
    assert "2 —" not in text


def test_render_dashboard_shows_connected_for_running_operation():
    state = ClientState(connected=False)

    text = render_dashboard(state, operation={"name": "play", "running": True, "stop_requested": False, "elapsed_seconds": 0.1})

    assert "Connected: yes" in text


def test_render_dashboard_includes_persistent_live_state():
    state = ClientState(
        host="10.0.0.41",
        port=8073,
        frequency_khz=10000.0,
        mode="usb",
        low_cut_hz=300,
        high_cut_hz=2700,
        duration_seconds=45,
        max_frames=1200,
        connected=True,
    )

    text = render_dashboard(
        state,
        {"type": "state", "active_command": "SET mod=am low_cut=-5000 high_cut=5000 freq=7000.000"},
        message="ok",
        operation={
            "name": "play",
            "running": True,
            "stop_requested": False,
            "elapsed_seconds": 1.25,
            "metrics": {
                "rssi_db": -42.0,
                "smeter": 850,
                "snd_frames": 7,
                "sample_rate_hz": 11999,
                "sequence_gaps": 1,
                "adc_overflows": 2,
            },
        },
    )

    assert "KiwiSDR Client" in text
    assert "Receiver: 10.0.0.41:8073" in text
    assert "Connected: yes" in text
    assert "Frequency: 10000.000 kHz" in text
    assert "Mode/filter: usb 300..2700 Hz" in text
    assert "Volume: 100%" in text
    assert "Live limits: 45s / 1200 SND frames" in text
    assert "Operation: play" in text
    assert "Running: yes" in text
    assert "RSSI/S-meter: -42.0 dB / 850" in text
    assert "SND frames: 7" in text
    assert "Sample rate: 11999 Hz" in text
    assert "Sequence gaps: 1" in text
    assert "ADC overflows: 2" in text
    assert "Last response: state" in text
    assert "Applied to active stream: SET mod=am low_cut=-5000 high_cut=5000 freq=7000.000" in text
    assert "Message: ok" in text


def test_render_dashboard_includes_batch_active_commands():
    state = ClientState()

    text = render_dashboard(
        state,
        {
            "type": "batch",
            "active_commands": [
                "SET mod=usb low_cut=100 high_cut=2400 freq=7000.000",
                "SET agc=1 hang=0 thresh=-100 slope=6 decay=1000 manGain=35",
            ],
        },
    )

    assert "Applied to active stream: SET mod=usb low_cut=100 high_cut=2400 freq=7000.000" in text
    assert "Applied to active stream: SET agc=1 hang=0 thresh=-100 slope=6 decay=1000 manGain=35" in text


class TuiFakeVolumeControl:
    def __init__(self):
        self.values = []

    def get_percent(self) -> int:
        return self.values[-1] if self.values else 10

    def set_percent(self, percent: int) -> dict:
        self.values.append(percent)
        return {"backend": "fake", "percent": percent}


class TuiFakeOperations:
    def __init__(self):
        self.play_configs = []

    def play(self, config, *, null_sink: bool, stop_event=None, command_queue=None, status_callback=None):
        self.play_configs.append(config)
        return {"frames": 1, "dry_run": null_sink}

    def record(self, config, *, stop_event=None, status_callback=None):
        return {"path": str(config.output)}

    def capture(self, config, *, stop_event=None, status_callback=None):
        return {"path": str(config.output)}


def test_tui_command_mode_executes_semicolon_batch():
    controller = ClientController()
    state = TuiInputState(mode=InputMode.COMMAND)

    for ch in "tu 7000; mo usb 300 2700":
        handle_tui_key(ord(ch), state, controller, load_config())
    response, message = handle_tui_key(10, state, controller, load_config())

    assert response["type"] == "batch"
    assert controller.state.frequency_khz == 7000.0
    assert controller.state.mode == "usb"
    assert message == ""
    assert state.mode == InputMode.KEYMAP


def test_tui_command_mode_pb_uses_configured_allow_live(tmp_path):
    config_path = tmp_path / "config.toml"
    config_path.write_text("[live]\nallow_live = true\n", encoding="utf-8")
    config = load_config(config_path)
    controller = ClientController(operations=TuiFakeOperations(), allow_live_default=config.live.allow_live)
    state = TuiInputState(mode=InputMode.COMMAND)

    for ch in "pb --null-sink":
        handle_tui_key(ord(ch), state, controller, config)
    response, message = handle_tui_key(10, state, controller, config)

    assert response["operation"]["name"] == "play"
    assert message == ""
    assert state.mode == InputMode.KEYMAP
    controller.execute("wait 1")


def test_tui_state_from_config_applies_live_limits_and_receiver_policy(tmp_path):
    config_path = tmp_path / "config.toml"
    config_path.write_text(
        """
[live]
duration_seconds = 0
max_frames = 0

[receivers]
restricted = false
allowed = ["example.com:8073"]
""".strip(),
        encoding="utf-8",
    )
    state = state_from_config(load_config(config_path))

    assert state.duration_seconds == 0
    assert state.max_frames == 0
    assert state.receivers_restricted is False
    assert state.allowed_receivers == ("example.com:8073",)


def test_tui_keymap_mode_executes_configured_tune_and_volume_actions(tmp_path):
    config_path = tmp_path / "config.toml"
    config_path.write_text(
        """
[steps]
medium_hz = 2500

[volume]
step_percent = 5
""".strip(),
        encoding="utf-8",
    )
    config = load_config(config_path)
    volume = TuiFakeVolumeControl()
    controller = ClientController(volume_control=volume)
    state = TuiInputState()

    response, message = handle_tui_key(ord("l"), state, controller, config)
    assert response["state"]["frequency_khz"] == 5002.5
    assert message == ""
    assert state.mode == InputMode.KEYMAP

    response, message = handle_tui_key(ord("k"), state, controller, config)
    assert response["state"]["volume_percent"] == 15
    assert response["volume"] == {"backend": "fake", "percent": 15}
    assert message == ""
    assert volume.values == [15]


def test_tui_expand_key_action_uses_configured_steps(tmp_path):
    config_path = tmp_path / "config.toml"
    config_path.write_text("[steps]\nlarge_hz = 12500\n", encoding="utf-8")
    config = load_config(config_path)

    assert expand_key_action("tune-step +large", ClientController(), config) == "tune 5012.500"


def test_tui_modified_and_unknown_keys_are_safe_in_keymap_mode():
    controller = ClientController()
    state = TuiInputState()

    if getattr(curses, "KEY_SRIGHT", None) is not None:
        assert normalize_key_name(curses.KEY_SRIGHT) == "shift-right"
        response, message = handle_tui_key(curses.KEY_SRIGHT, state, controller, load_config())
        assert response["state"]["frequency_khz"] == 5000.1
        assert message == ""

    response, message = handle_tui_key(27, state, controller, load_config())
    assert response is None
    assert message is None
    assert controller.running is True

    response, message = handle_tui_key(9999, state, controller, load_config())
    assert response is None
    assert message is None
    assert controller.running is True


def test_tui_keymap_quit_stops_background_operation_before_exit():
    controller = ClientController()

    def target(stop_event, command_queue, status_callback):
        while not stop_event.is_set():
            time.sleep(0.01)
        return {"stopped": True}

    controller.background.start("play", target)
    response, message = handle_tui_key(ord("q"), TuiInputState(), controller, load_config())

    assert controller.running is False
    assert response["operation"]["running"] is False
    assert response["operation"]["result"] == {"stopped": True}
    assert message == "Stopped background operation and quitting."


def test_tui_command_mode_quit_stops_background_operation_before_exit():
    controller = ClientController()

    def target(stop_event, command_queue, status_callback):
        while not stop_event.is_set():
            time.sleep(0.01)
        return {"stopped": True}

    controller.background.start("play", target)
    state = TuiInputState(mode=InputMode.COMMAND, command="q")
    response, message = handle_tui_key(10, state, controller, load_config())

    assert controller.running is False
    assert response["operation"]["running"] is False
    assert response["operation"]["result"] == {"stopped": True}
    assert message == "Stopped background operation and quitting."


def test_tui_safe_quit_keeps_running_when_operation_does_not_stop_quickly():
    controller = ClientController()

    def target(stop_event, command_queue, status_callback):
        time.sleep(0.2)
        return {"stopped": stop_event.is_set()}

    controller.background.start("play", target)
    response, message = request_tui_quit(controller, join_timeout=0.01)

    assert controller.running is True
    assert response["operation"]["running"] is True
    assert message == "Stopping background operation before quit..."
    controller.background.stop()
    controller.background.join(timeout=1.0)


def test_tui_keymap_prefix_sequences_store_and_recall_presets():
    controller = ClientController(volume_control=TuiFakeVolumeControl())
    state = TuiInputState()

    response, message = handle_tui_key(ord("s"), state, controller, load_config())
    assert response is None
    assert message == "Store preset: press register [0..9] or [a..z]"
    response, message = handle_tui_key(ord("a"), state, controller, load_config())
    assert response["type"] == "preset"
    assert response["preset"] == "a"
    assert response["scope"] == "minimal"

    controller.execute("agc gain 25")
    handle_tui_key(ord("S"), state, controller, load_config())
    response, message = handle_tui_key(ord("b"), state, controller, load_config())
    assert response["preset"] == "b"
    assert response["scope"] == "all"

    controller.execute("agc gain 50")
    handle_tui_key(ord("p"), state, controller, load_config())
    response, message = handle_tui_key(ord("b"), state, controller, load_config())
    assert response["preset"] == "b"
    assert response["state"]["agc_gain"] == 25


class TuiBlockingOperations(TuiFakeOperations):
    def play(self, config, *, null_sink: bool, stop_event=None, command_queue=None, status_callback=None):
        self.play_configs.append(config)
        if stop_event is not None:
            deadline = time.monotonic() + 1.0
            while not stop_event.is_set() and time.monotonic() < deadline:
                time.sleep(0.01)
        return {"receiver": f"{config.host}:{config.port}", "stopped": bool(stop_event and stop_event.is_set())}


class TuiFailFirstReceiverOperations(TuiBlockingOperations):
    def play(self, config, *, null_sink: bool, stop_event=None, command_queue=None, status_callback=None):
        self.play_configs.append(config)
        receiver = f"{config.host}:{config.port}"
        if receiver == "10.0.0.42:8073":
            raise RuntimeError("server busy or bad password: all no-password channels may be busy on 10.0.0.42:8073")
        if stop_event is not None:
            deadline = time.monotonic() + 1.0
            while not stop_event.is_set() and time.monotonic() < deadline:
                time.sleep(0.01)
        return {"receiver": receiver, "stopped": bool(stop_event and stop_event.is_set())}


class TuiBusyNewReceiverOperations(TuiBlockingOperations):
    def play(self, config, *, null_sink: bool, stop_event=None, command_queue=None, status_callback=None):
        self.play_configs.append(config)
        receiver = f"{config.host}:{config.port}"
        if receiver == "10.0.0.40:8073":
            raise RuntimeError("server busy: all 4 client slots are taken on 10.0.0.40:8073")
        if stop_event is not None:
            deadline = time.monotonic() + 1.0
            while not stop_event.is_set() and time.monotonic() < deadline:
                time.sleep(0.01)
        return {"receiver": receiver, "stopped": bool(stop_event and stop_event.is_set())}


def test_tui_keymap_stored_receiver_prefix_switches_receiver():
    controller = ClientController(volume_control=TuiFakeVolumeControl())
    controller.execute("add-receiver a http://10.0.0.42:8073/ Backup receiver")
    state = TuiInputState()

    response, message = handle_tui_key(ord("r"), state, controller, load_config())
    assert response is None
    assert message == "Receiver: press register [0..9] or [a..z]"
    response, message = handle_tui_key(ord("a"), state, controller, load_config())

    assert message == "Receiver: 10.0.0.42:8073"
    assert response["state"]["receiver"] == "10.0.0.42:8073"


def test_tui_keymap_numeric_stored_receiver_register_switches_receiver():
    controller = ClientController(volume_control=TuiFakeVolumeControl())
    controller.execute("add-receiver 2 http://10.0.0.42:8073/ Backup receiver")
    state = TuiInputState()

    handle_tui_key(ord("r"), state, controller, load_config())
    response, message = handle_tui_key(ord("2"), state, controller, load_config())

    assert message == "Receiver: 10.0.0.42:8073"
    assert response["state"]["receiver"] == "10.0.0.42:8073"


def test_tui_add_receiver_command_persists_to_config_allowlist(tmp_path):
    config_path = tmp_path / "config.toml"
    config_path.write_text(
        """
[receivers]
restricted = false
allowed = ["10.0.0.40:8073"]
""".strip() + "\n",
        encoding="utf-8",
    )
    config = load_config(config_path)
    controller = ClientController(volume_control=TuiFakeVolumeControl())
    state = TuiInputState(mode=InputMode.COMMAND, command="ad 2 http://10.0.0.42:8073 Backup receiver")

    response, message = handle_tui_key(10, state, controller, config)

    assert response["type"] == "receiver-preset"
    assert message == "Saved receiver(s) to config: 10.0.0.42:8073"
    assert load_config(config_path).receivers.allowed == ("10.0.0.40:8073", "10.0.0.42:8073")


def test_tui_add_receiver_command_does_not_duplicate_config_allowlist(tmp_path):
    config_path = tmp_path / "config.toml"
    config_path.write_text(
        """
[receivers]
restricted = false
allowed = ["10.0.0.40:8073", "10.0.0.42:8073"]
""".strip() + "\n",
        encoding="utf-8",
    )
    config = load_config(config_path)
    controller = ClientController(volume_control=TuiFakeVolumeControl())
    state = TuiInputState(mode=InputMode.COMMAND, command="ad 2 http://10.0.0.42:8073 Backup receiver")

    response, message = handle_tui_key(10, state, controller, config)

    assert response["type"] == "receiver-preset"
    assert message == ""
    assert config_path.read_text(encoding="utf-8").count("10.0.0.42:8073") == 1


def test_tui_keymap_receiver_prefix_switches_receiver_and_preserves_radio_parameters(tmp_path):
    config_path = tmp_path / "config.toml"
    config_path.write_text(
        """
[receivers]
allowed = ["10.0.0.41:8073", "10.0.0.40:8073"]
""".strip(),
        encoding="utf-8",
    )
    config = load_config(config_path)
    controller = ClientController(volume_control=TuiFakeVolumeControl())
    controller.execute("tune 7100")
    controller.execute("mode usb 300 2700")
    state = TuiInputState()

    response, message = handle_tui_key(ord("r"), state, controller, config)
    assert response is None
    assert message == "Receiver: press register [0..9] or [a..z]"
    response, message = handle_tui_key(ord("1"), state, controller, config)

    assert response["type"] == "state"
    assert message == "Receiver: 10.0.0.40:8073"
    assert response["state"]["receiver"] == "10.0.0.40:8073"
    assert response["state"]["frequency_khz"] == 7100.0
    assert response["state"]["mode"] == "usb"
    assert response["state"]["low_cut_hz"] == 300
    assert response["state"]["high_cut_hz"] == 2700


def test_tui_receiver_switch_restarts_active_background_playback(tmp_path):
    config_path = tmp_path / "config.toml"
    config_path.write_text(
        """
[live]
allow_live = true

[receivers]
allowed = ["10.0.0.41:8073", "10.0.0.40:8073"]
""".strip(),
        encoding="utf-8",
    )
    config = load_config(config_path)
    operations = TuiBlockingOperations()
    controller = ClientController(operations=operations, allow_live_default=True)
    state = TuiInputState()

    controller.execute("play-bg --null-sink")
    handle_tui_key(ord("r"), state, controller, config)
    response, message = handle_tui_key(ord("1"), state, controller, config)
    controller.execute("stop")
    controller.execute("wait 2")

    assert message == "Receiver: 10.0.0.40:8073; restarted playback"
    assert response["type"] == "batch"
    assert controller.state.receiver == "10.0.0.40:8073"
    assert [f"{config.host}:{config.port}" for config in operations.play_configs] == ["10.0.0.41:8073", "10.0.0.40:8073"]


def test_tui_receiver_switch_after_failed_playback_starts_new_receiver(tmp_path):
    config_path = tmp_path / "config.toml"
    config_path.write_text(
        """
[live]
allow_live = true

[receivers]
allowed = ["10.0.0.42:8073", "10.0.0.41:8073"]
""".strip(),
        encoding="utf-8",
    )
    config = load_config(config_path)
    operations = TuiFailFirstReceiverOperations()
    controller = ClientController(operations=operations, allow_live_default=True)
    state = TuiInputState()
    controller.execute("receiver 10.0.0.42:8073")

    controller.execute("play-bg --null-sink")
    failed = controller.execute("wait 1")
    handle_tui_key(ord("r"), state, controller, config)
    response, message = handle_tui_key(ord("1"), state, controller, config)
    running = controller.background.status()
    controller.execute("stop")
    controller.execute("wait 2")

    assert "server busy" in failed["operation"]["error"]
    assert message == "Receiver: 10.0.0.41:8073; started playback"
    assert response["type"] == "batch"
    assert controller.state.receiver == "10.0.0.41:8073"
    assert running.running is True
    assert running.error is None
    assert [f"{play_config.host}:{play_config.port}" for play_config in operations.play_configs] == [
        "10.0.0.42:8073",
        "10.0.0.41:8073",
    ]


def test_tui_receiver_switch_busy_restores_previous_receiver_and_reports_error(tmp_path):
    config_path = tmp_path / "config.toml"
    config_path.write_text(
        """
[live]
allow_live = true

[receivers]
allowed = ["10.0.0.41:8073", "10.0.0.40:8073"]
""".strip(),
        encoding="utf-8",
    )
    config = load_config(config_path)
    operations = TuiBusyNewReceiverOperations()
    controller = ClientController(operations=operations, allow_live_default=True)
    state = TuiInputState()

    controller.execute("play-bg --null-sink")
    handle_tui_key(ord("r"), state, controller, config)
    response, message = handle_tui_key(ord("1"), state, controller, config)
    controller.execute("stop")
    controller.execute("wait 2")

    assert controller.state.receiver == "10.0.0.41:8073"
    assert "server busy" in message
    assert "restored receiver: 10.0.0.41:8073" in message
    assert response["type"] == "operation-status"
    assert [f"{play_config.host}:{play_config.port}" for play_config in operations.play_configs] == [
        "10.0.0.41:8073",
        "10.0.0.40:8073",
        "10.0.0.41:8073",
    ]


def test_tui_startup_playback_starts_background_worker(tmp_path, monkeypatch):
    config_path = tmp_path / "config.toml"
    config_path.write_text(
        """
[live]
allow_live = true

[startup]
playback = true
""".strip(),
        encoding="utf-8",
    )
    config = load_config(config_path)
    operations = TuiBlockingOperations()
    controller = ClientController(operations=operations)
    captured = {}

    def fake_wrapper(func, controller_arg, config_arg):
        captured["running"] = controller_arg.background.status().running
        captured["receiver"] = controller_arg.state.receiver
        controller_arg.background.stop()
        controller_arg.background.join(timeout=1.0)

    monkeypatch.setattr("kiwi_client.tui.curses.wrapper", fake_wrapper)

    run_tui(controller, config=config)

    assert captured["running"] is True
    assert [f"{play_config.host}:{play_config.port}" for play_config in operations.play_configs] == [captured["receiver"]]


def test_tui_startup_playback_respects_live_guard(tmp_path):
    config_path = tmp_path / "config.toml"
    config_path.write_text(
        """
[live]
allow_live = false

[startup]
playback = true
""".strip(),
        encoding="utf-8",
    )
    config = load_config(config_path)
    controller = ClientController(operations=TuiBlockingOperations())

    response = start_startup_playback(controller, config)

    assert response is None
    assert controller.background.status().running is False


def test_tui_safe_quit_persists_receiver_registers(tmp_path):
    config_path = tmp_path / "config.toml"
    state_path = tmp_path / "state.json"
    config_path.write_text(
        f"""
[startup]
mode = "last"
state_file = "{state_path}"
""".strip(),
        encoding="utf-8",
    )
    config = load_config(config_path)
    controller = ClientController(volume_control=TuiFakeVolumeControl())
    controller.execute("add-receiver a 10.0.0.42:8073 Backup receiver")

    request_tui_quit(controller, config=config)
    restarted = ClientController()
    run_config_state, run_presets = startup_state_and_presets(config)
    restarted.state = run_config_state
    restarted.presets.update(run_presets)
    restarted.receiver_presets.update(startup_receiver_presets(config))
    text = render_tui_hints(TuiInputState(pending_key_action="receiver"), config, restarted)

    assert "a — 10.0.0.42:8073 Backup receiver" in text
    assert "receiver_presets" not in state_path.read_text(encoding="utf-8")
    assert "[receiver_presets.a]" in (tmp_path / "presets.toml").read_text(encoding="utf-8")


def test_tui_startup_state_and_safe_quit_persist_state(tmp_path):
    config_path = tmp_path / "config.toml"
    state_path = tmp_path / "state.json"
    config_path.write_text(
        f"""
[startup]
mode = "last"
state_file = "{state_path}"

[default_state]
frequency_khz = 6000.0
""".strip(),
        encoding="utf-8",
    )
    config = load_config(config_path)
    state, presets = startup_state_and_presets(config)
    controller = ClientController(state=state, presets=presets, volume_control=TuiFakeVolumeControl())
    controller.execute("tune 7100")
    controller.execute("store all 3")

    response, message = request_tui_quit(controller, config=config)
    restored_state, restored_presets = startup_state_and_presets(config)

    assert response["type"] == "quit"
    assert restored_state.frequency_khz == 7100.0
    assert restored_presets[3]["frequency_khz"] == 7100.0
    state_json = json.loads(state_path.read_text(encoding="utf-8"))
    assert set(state_json) == {"last_state"}
    assert "[radio_presets.\"3\"]" in (tmp_path / "presets.toml").read_text(encoding="utf-8")


def test_run_tui_does_not_overwrite_restored_last_state(tmp_path, monkeypatch):
    config_path = tmp_path / "config.toml"
    state_path = tmp_path / "state.json"
    config_path.write_text(
        f"""
[startup]
mode = "last"
state_file = "{state_path}"

[default_state]
frequency_khz = 6000.0
mode = "am"
""".strip(),
        encoding="utf-8",
    )
    config = load_config(config_path)
    controller = ClientController(volume_control=TuiFakeVolumeControl())
    controller.execute("tune 7100")
    controller.execute("mode usb 300 2700")
    request_tui_quit(controller, config=config)
    restored_state, restored_presets = startup_state_and_presets(config)
    captured = {}

    def fake_wrapper(func, controller_arg, config_arg):
        captured["state"] = controller_arg.state
        captured["config"] = config_arg

    monkeypatch.setattr("kiwi_client.tui.curses.wrapper", fake_wrapper)

    run_tui(ClientController(state=restored_state, presets=restored_presets), config=config)

    assert captured["state"].frequency_khz == 7100.0
    assert captured["state"].mode == "usb"
    assert captured["state"].low_cut_hz == 300
    assert captured["state"].high_cut_hz == 2700


def test_tui_startup_can_restore_configured_preset(tmp_path):
    config_path = tmp_path / "config.toml"
    state_path = tmp_path / "state.json"
    config_path.write_text(
        f"""
[startup]
mode = "preset"
preset = 4
state_file = "{state_path}"
""".strip(),
        encoding="utf-8",
    )
    config = load_config(config_path)
    controller = ClientController(volume_control=TuiFakeVolumeControl())
    controller.execute("tune 8200")
    controller.execute("store all 4")
    request_tui_quit(controller, config=config)

    restored_state, restored_presets = startup_state_and_presets(config)

    assert restored_state.frequency_khz == 8200.0
    assert 4 in restored_presets


def test_tui_command_mode_executes_and_exits_to_keymap():
    controller = ClientController()
    state = TuiInputState()

    response, message = handle_tui_key(ord(":"), state, controller)
    assert response is None
    assert message == ""
    assert state.mode == InputMode.COMMAND

    for ch in "tune 7000":
        handle_tui_key(ord(ch), state, controller)
    response, message = handle_tui_key(10, state, controller)

    assert response["state"]["frequency_khz"] == 7000.0
    assert message == ""
    assert state.mode == InputMode.KEYMAP
    assert state.command == ""
    assert state.history == ["tune 7000"]


def test_tui_command_mode_escape_clears_command_without_quitting():
    controller = ClientController()
    state = TuiInputState(mode=InputMode.COMMAND, command="tune 7000")

    response, message = handle_tui_key(27, state, controller)

    assert response is None
    assert message == ""
    assert state.mode == InputMode.KEYMAP
    assert state.command == ""
    assert controller.running is True


def test_tui_command_history_up_down_selects_command_for_editing():
    controller = ClientController()
    state = TuiInputState(mode=InputMode.COMMAND, history=["tune 5000", "mode am -5000 5000"])

    handle_tui_key(curses.KEY_UP, state, controller)
    assert state.command == "mode am -5000 5000"
    handle_tui_key(curses.KEY_UP, state, controller)
    assert state.command == "tune 5000"
    handle_tui_key(curses.KEY_DOWN, state, controller)
    assert state.command == "mode am -5000 5000"

    handle_tui_key(ord(" "), state, controller)
    handle_tui_key(ord("#"), state, controller)
    assert state.command == "mode am -5000 5000 #"


def test_tui_module_has_python_m_entrypoint():
    source = Path("src/kiwi_client/tui.py").read_text(encoding="utf-8")

    assert 'if __name__ == "__main__"' in source
    assert "raise SystemExit(main())" in source


def test_tui_uses_periodic_input_timeout_for_status_refresh():
    source = Path("src/kiwi_client/tui.py").read_text(encoding="utf-8")

    assert "stdscr.timeout(250)" in source
    assert "if ch == -1:" in source
