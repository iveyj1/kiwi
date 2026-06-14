from pathlib import Path

import curses
import time

from kiwi_client.client_app import ClientController, ClientState
from kiwi_client.config import load_config
from kiwi_client.tui import (
    InputMode,
    TuiInputState,
    expand_key_action,
    handle_tui_key,
    normalize_key_name,
    render_dashboard,
    request_tui_quit,
    startup_state_and_presets,
    state_from_config,
)


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


class TuiFakeVolumeControl:
    def __init__(self):
        self.values = []

    def get_percent(self) -> int:
        return self.values[-1] if self.values else 10

    def set_percent(self, percent: int) -> dict:
        self.values.append(percent)
        return {"backend": "fake", "percent": percent}


class TuiFakeOperations:
    def play(self, config, *, null_sink: bool, stop_event=None, command_queue=None, status_callback=None):
        return {"frames": 1, "dry_run": null_sink}

    def record(self, config, *, stop_event=None, status_callback=None):
        return {"path": str(config.output)}

    def capture(self, config, *, stop_event=None, status_callback=None):
        return {"path": str(config.output)}


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


def test_tui_keymap_digit_sequences_store_and_recall_presets():
    controller = ClientController(volume_control=TuiFakeVolumeControl())
    state = TuiInputState()

    response, message = handle_tui_key(ord("1"), state, controller, load_config())
    assert response is None
    assert message == "Preset 1: press s=store, S=store all, r=recall"
    response, message = handle_tui_key(ord("s"), state, controller, load_config())
    assert response["type"] == "preset"
    assert response["scope"] == "minimal"

    controller.execute("agc gain 25")
    handle_tui_key(ord("2"), state, controller, load_config())
    response, message = handle_tui_key(ord("S"), state, controller, load_config())
    assert response["scope"] == "all"

    controller.execute("agc gain 50")
    handle_tui_key(ord("2"), state, controller, load_config())
    response, message = handle_tui_key(ord("r"), state, controller, load_config())
    assert response["preset"] == 2
    assert response["state"]["agc_gain"] == 25


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
