from kiwi_client.client_app import ClientState
from kiwi_client.state_store import (
    apply_preset,
    full_preset,
    load_presets_file,
    load_state_file,
    minimal_preset,
    save_presets_file,
    save_state_file,
)

import pytest


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


def test_save_and_load_letter_register_presets(tmp_path):
    path = tmp_path / "presets.toml"
    state = ClientState(frequency_khz=7100.0)

    save_presets_file(path, presets={"a": full_preset(state), 1: minimal_preset(state)}, receiver_presets={})
    loaded = load_presets_file(path)

    assert loaded["presets"]["a"]["frequency_khz"] == 7100.0
    assert loaded["presets"]["1"]["frequency_khz"] == 7100.0


def test_save_and_load_presets_file(tmp_path):
    path = tmp_path / "presets.toml"
    state = ClientState(frequency_khz=7100.0, mode="usb", agc_gain=25)

    save_presets_file(
        path,
        presets={"a": full_preset(state), 1: minimal_preset(state)},
        receiver_presets={"2": {"receiver": "10.0.0.42:8073", "description": "Backup receiver"}},
    )
    loaded = load_presets_file(path)

    assert loaded["presets"]["a"]["frequency_khz"] == 7100.0
    assert loaded["presets"]["1"]["mode"] == "usb"
    assert loaded["receiver_presets"]["2"] == {"receiver": "10.0.0.42:8073", "description": "Backup receiver"}


def test_save_and_load_state_file_only_persists_last_state(tmp_path):
    path = tmp_path / "state.json"
    state = ClientState(frequency_khz=7000.0, agc_gain=25)

    save_state_file(path, last_state=state)
    loaded = load_state_file(path)

    assert loaded["last_state"]["frequency_khz"] == 7000.0
    assert loaded["last_state"]["agc_gain"] == 25
    assert "allowed_receivers" not in loaded["last_state"]
    assert "audio_startup_mute_ms" not in loaded["last_state"]
    assert "presets" not in path.read_text(encoding="utf-8")
    assert loaded == {"last_state": loaded["last_state"]}


def test_load_state_file_rejects_old_durable_keys(tmp_path):
    path = tmp_path / "state.json"
    path.write_text('{"last_state": null, "presets": {}, "receiver_presets": {}}\n', encoding="utf-8")

    with pytest.raises(ValueError, match="unsupported state file keys"):
        load_state_file(path)
