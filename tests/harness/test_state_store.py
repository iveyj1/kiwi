from kiwi_client.client_app import ClientState
from kiwi_client.state_store import apply_preset, full_preset, load_state_file, minimal_preset, save_state_file


def test_minimal_and_full_presets():
    state = ClientState(host="10.0.0.41", frequency_khz=7000.0, mode="usb", low_cut_hz=300, high_cut_hz=2700, agc_gain=25)

    minimal = minimal_preset(state)
    full = full_preset(state)

    assert minimal == {
        "host": "10.0.0.41",
        "port": 8073,
        "frequency_khz": 7000.0,
        "mode": "usb",
        "low_cut_hz": 300,
        "high_cut_hz": 2700,
    }
    assert full["agc_gain"] == 25
    assert full["allowed_receivers"] == ["10.0.0.40:8073", "10.0.0.41:8073"]


def test_apply_preset_preserves_unspecified_fields():
    state = ClientState(agc_gain=25)

    applied = apply_preset(state, {"frequency_khz": 7000.0, "mode": "usb"})

    assert applied.frequency_khz == 7000.0
    assert applied.mode == "usb"
    assert applied.agc_gain == 25


def test_save_and_load_state_file(tmp_path):
    path = tmp_path / "state.json"
    state = ClientState(frequency_khz=7000.0, agc_gain=25)
    presets = {1: minimal_preset(state), 2: full_preset(state)}

    save_state_file(path, last_state=state, presets=presets)
    loaded = load_state_file(path)

    assert loaded["last_state"]["frequency_khz"] == 7000.0
    assert loaded["presets"]["1"]["frequency_khz"] == 7000.0
    assert loaded["presets"]["2"]["agc_gain"] == 25
