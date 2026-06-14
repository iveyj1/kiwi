from pathlib import Path

from kiwi_client.config import default_config, load_config
from kiwi_client.tui import build_arg_parser


def test_default_config_has_keymaps_and_steps():
    config = default_config()

    assert config.steps.small_hz == 100
    assert config.steps.medium_hz == 1000
    assert config.steps.large_hz == 5000
    assert config.volume.step_percent == 10
    assert config.live.allow_live is False
    assert config.live.duration_seconds == 60.0
    assert config.live.max_frames == 1500
    assert config.receivers.restricted is True
    assert config.receivers.allowed == ("10.0.0.40:8073", "10.0.0.41:8073")
    assert config.startup.mode == "last"
    assert config.startup.preset == 1
    assert config.startup.state_file.endswith("kiwi-client/state.json")
    assert config.default_state["frequency_khz"] == 5000.0
    assert config.keys["right"] == "tune-step +medium"
    assert config.keys["l"] == "tune-step +medium"
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

[live]
allow_live = true
duration_seconds = 0
max_frames = 0

[receivers]
restricted = false
allowed = ["example.com:8073"]

[startup]
mode = "preset"
preset = 7
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
    assert config.live.allow_live is True
    assert config.live.duration_seconds == 0
    assert config.live.max_frames == 0
    assert config.receivers.restricted is False
    assert config.receivers.allowed == ("example.com:8073",)
    assert config.startup.mode == "preset"
    assert config.startup.preset == 7
    assert config.startup.state_file == "state.json"
    assert config.default_state["frequency_khz"] == 1234.5
    assert config.default_state["mode"] == "usb"
    assert config.keys["right"] == "tune-step +medium"
    assert config.keys["l"] == "tune-step +large"
    assert config.keys["x"] == "stop"


def test_tui_parser_accepts_config_path(tmp_path: Path):
    path = tmp_path / "config.toml"

    args = build_arg_parser().parse_args(["--config", str(path)])

    assert args.config == path
