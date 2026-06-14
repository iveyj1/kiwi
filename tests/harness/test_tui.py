from pathlib import Path

from kiwi_client.client_app import ClientState
from kiwi_client.tui import render_dashboard


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


def test_tui_module_has_python_m_entrypoint():
    source = Path("src/kiwi_client/tui.py").read_text(encoding="utf-8")

    assert 'if __name__ == "__main__"' in source
    assert "raise SystemExit(main())" in source


def test_tui_uses_periodic_input_timeout_for_status_refresh():
    source = Path("src/kiwi_client/tui.py").read_text(encoding="utf-8")

    assert "stdscr.timeout(250)" in source
    assert "if ch == -1:" in source
