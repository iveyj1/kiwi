from pathlib import Path

import curses

from kiwi_client.client_app import ClientController, ClientState
from kiwi_client.tui import InputMode, TuiInputState, handle_tui_key, render_dashboard


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
