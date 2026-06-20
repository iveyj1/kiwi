from pathlib import Path

from kiwi_client.config import add_allowed_receiver_to_config, default_config, discover_config_path, load_config, resolve_presets_path, resolve_state_path
from kiwi_client.tui import build_arg_parser


def test_default_config_has_keymaps_and_steps():
    config = default_config()

    assert config.steps.small_hz == 100
    assert config.steps.medium_hz == 1000
    assert config.steps.large_hz == 5000
    assert config.volume.step_percent == 10
    assert config.audio.startup_mute_ms == 300
    assert config.audio.startup_fade_in_ms == 100
    assert config.audio.stop_fade_out_ms == 100
    assert config.live.allow_live is False
    assert config.live.duration_seconds == 60.0
    assert config.live.max_frames == 1500
    assert config.receivers.restricted is True
    assert config.receivers.allowed == ("10.0.0.40:8073", "10.0.0.41:8073")
    assert config.presets.file == "presets.toml"
    assert config.tuning.cw_offset_hz == -800
    assert config.tuning.mode_passbands["am"] == (-5000, 5000)
    assert config.tuning.mode_passbands["usb"] == (0, 3000)
    assert config.tuning.mode_passbands["lsb"] == (-3000, 0)
    assert config.tuning.mode_passbands["cw"] == (650, 1050)
    assert config.tuning.mode_step_pairs["am"] == ((5000, 1000),)
    assert config.tuning.mode_step_pairs["usb"] == ((1000, 100),)
    assert config.tuning.mode_step_pairs["lsb"] == ((1000, 100),)
    assert config.tuning.mode_step_pairs["cw"] == ((100, 10),)
    assert config.startup.mode == "last"
    assert config.startup.preset == 1
    assert config.startup.playback is False
    assert config.startup.state_file.endswith("kiwi-client/state.json")
    assert config.default_state["frequency_khz"] == 5000.0
    assert config.keys["right"] == "tune-step +mode"
    assert config.keys["l"] == "tune-step +mode"
    assert config.keys["shift-l"] == "tune-step +mode-small"
    assert config.keys["t"] == "step-pair +1"
    assert config.keys["shift-t"] == "step-pair -1"
    assert config.keys["up"] == "volume-step +10"
    assert config.keys[":"] == "command-mode"


def test_load_config_overlays_defaults(tmp_path: Path):
    path = tmp_path / "config.toml"
    path.write_text(
        """
[steps]
medium_hz = 2500

[volume]
step_percent = 5

[audio]
startup_mute_ms = 125
startup_fade_in_ms = 50
stop_fade_out_ms = 75

[live]
allow_live = true
duration_seconds = 0
max_frames = 0

[receivers]
restricted = false
allowed = ["example.com:8073"]

[presets]
file = "my-presets.toml"

[tuning]
cw_offset_hz = -700

[tuning.mode_passbands.usb]
low_cut_hz = 100
high_cut_hz = 2400

[tuning.mode_steps.usb]
pairs = [[1000, 100], [2500, 250]]

[startup]
mode = "preset"
preset = 7
playback = true
state_file = "state.json"

[default_state]
frequency_khz = 1234.5
mode = "usb"

[keys]
"l" = "tune-step +large"
"x" = "stop"
""".strip(),
        encoding="utf-8",
    )

    config = load_config(path)

    assert config.steps.small_hz == 100
    assert config.steps.medium_hz == 2500
    assert config.steps.large_hz == 5000
    assert config.volume.step_percent == 5
    assert config.audio.startup_mute_ms == 125
    assert config.audio.startup_fade_in_ms == 50
    assert config.audio.stop_fade_out_ms == 75
    assert config.live.allow_live is True
    assert config.live.duration_seconds == 0
    assert config.live.max_frames == 0
    assert config.receivers.restricted is False
    assert config.receivers.allowed == ("example.com:8073",)
    assert config.presets.file == "my-presets.toml"
    assert config.tuning.cw_offset_hz == -700
    assert config.tuning.mode_passbands["usb"] == (100, 2400)
    assert config.tuning.mode_passbands["am"] == (-5000, 5000)
    assert config.tuning.mode_step_pairs["usb"] == ((1000, 100), (2500, 250))
    assert config.tuning.mode_step_pairs["am"] == ((5000, 1000),)
    assert resolve_presets_path(config) == tmp_path / "my-presets.toml"
    assert resolve_state_path(config) == tmp_path / "state.json"
    assert config.startup.mode == "preset"
    assert config.startup.preset == 7
    assert config.startup.playback is True
    assert config.startup.state_file == "state.json"
    assert config.default_state["frequency_khz"] == 1234.5
    assert config.default_state["mode"] == "usb"
    assert config.keys["right"] == "tune-step +mode"
    assert config.keys["l"] == "tune-step +large"
    assert config.keys["x"] == "stop"


def test_add_allowed_receiver_to_config_appends_missing_receiver(tmp_path: Path):
    path = tmp_path / "config.toml"
    path.write_text(
        """
[receivers]
restricted = true
allowed = ["10.0.0.40:8073"]
""".strip() + "\n",
        encoding="utf-8",
    )

    changed = add_allowed_receiver_to_config(path, "10.0.0.42:8073")
    unchanged = add_allowed_receiver_to_config(path, "10.0.0.42:8073")
    config = load_config(path)

    assert changed is True
    assert unchanged is False
    assert config.receivers.allowed == ("10.0.0.40:8073", "10.0.0.42:8073")
    assert path.read_text(encoding="utf-8").count("10.0.0.42:8073") == 1


def test_discover_config_path_prefers_explicit_then_cwd_then_user(tmp_path: Path, monkeypatch):
    explicit = tmp_path / "explicit.toml"
    cwd_config = tmp_path / "config.toml"
    user_config = tmp_path / "home" / ".config" / "kiwi-client" / "config.toml"
    explicit.write_text("[live]\nallow_live = true\n", encoding="utf-8")
    cwd_config.write_text("[live]\nallow_live = true\n", encoding="utf-8")
    user_config.parent.mkdir(parents=True)
    user_config.write_text("[live]\nallow_live = true\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("HOME", str(tmp_path / "home"))

    assert discover_config_path(explicit) == explicit
    assert discover_config_path(None) == cwd_config
    cwd_config.unlink()
    assert discover_config_path(None) == user_config


def test_project_root_example_config_parses():
    config = load_config(Path("config.toml"))

    assert config.keys[":"] == "command-mode"
    assert config.receivers.allowed
    assert config.startup.playback is True


def test_tui_parser_accepts_config_path(tmp_path: Path):
    path = tmp_path / "config.toml"

    args = build_arg_parser().parse_args(["--config", str(path)])

    assert args.config == path
