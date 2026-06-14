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

    text = render_dashboard(state, {"type": "play", "result": {"frames": 1024}}, message="ok")

    assert "KiwiSDR Client" in text
    assert "Receiver: 10.0.0.41:8073" in text
    assert "Connected: yes" in text
    assert "Frequency: 10000.000 kHz" in text
    assert "Mode/filter: usb 300..2700 Hz" in text
    assert "Live limits: 45s / 1200 SND frames" in text
    assert "Last response: play" in text
    assert "Message: ok" in text
