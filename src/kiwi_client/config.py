"""User configuration loading for the KiwiSDR client."""

from __future__ import annotations

import tomllib
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any


DEFAULT_CONFIG_TOML = """
[steps]
small_hz = 100
medium_hz = 1000
large_hz = 5000

[volume]
step_percent = 10

[audio]
startup_mute_ms = 300
startup_fade_in_ms = 100
stop_fade_out_ms = 100

[live]
allow_live = false
duration_seconds = 60
max_frames = 1500

[receivers]
restricted = true
allowed = ["10.0.0.40:8073", "10.0.0.41:8073"]

[startup]
state_file = "~/.local/state/kiwi-client/state.json"
mode = "last"
preset = 1
playback = false

[default_state]
host = "10.0.0.40"
port = 8073
frequency_khz = 5000.0
mode = "am"
low_cut_hz = -5000
high_cut_hz = 5000

[keys]
# Direct key actions remain configurable. Built-in prefix keymaps are:
# p <register> = recall preset; s <register> = store minimal preset;
# S <register> = store full preset; r <receiver-register> = switch receiver.
# Registers are 0..9 and a..z. Receiver registers first use stored add-receiver entries,
# then map to [receivers].allowed order.
"right" = "tune-step +medium"
"l" = "tune-step +medium"
"left" = "tune-step -medium"
"h" = "tune-step -medium"
"shift-right" = "tune-step +small"
"shift-l" = "tune-step +small"
"shift-left" = "tune-step -small"
"shift-h" = "tune-step -small"
"ctrl-right" = "tune-step +large"
"ctrl-l" = "tune-step +large"
"ctrl-left" = "tune-step -large"
"ctrl-h" = "tune-step -large"
"up" = "volume-step +10"
"k" = "volume-step +10"
"down" = "volume-step -10"
"j" = "volume-step -10"
":" = "command-mode"
"q" = "quit"
"""


@dataclass(frozen=True)
class StepConfig:
    """Frequency step sizes in Hz."""

    small_hz: int = 100
    medium_hz: int = 1000
    large_hz: int = 5000


@dataclass(frozen=True)
class VolumeConfig:
    """Volume control settings."""

    step_percent: int = 10


@dataclass(frozen=True)
class AudioConfig:
    """Audio playback settings."""

    startup_mute_ms: int = 300
    startup_fade_in_ms: int = 100
    stop_fade_out_ms: int = 100


@dataclass(frozen=True)
class LiveConfig:
    """Live-operation guard settings."""

    allow_live: bool = False
    duration_seconds: float = 60.0
    max_frames: int = 1500


@dataclass(frozen=True)
class ReceiverConfig:
    """Receiver allowlist settings."""

    restricted: bool = True
    allowed: tuple[str, ...] = ("10.0.0.40:8073", "10.0.0.41:8073")


@dataclass(frozen=True)
class StartupConfig:
    """TUI startup/restore settings."""

    state_file: str = "~/.local/state/kiwi-client/state.json"
    mode: str = "last"
    preset: int = 1
    playback: bool = False


@dataclass(frozen=True)
class KiwiClientConfig:
    """Loaded client configuration."""

    source_path: str | None = None
    steps: StepConfig = field(default_factory=StepConfig)
    volume: VolumeConfig = field(default_factory=VolumeConfig)
    audio: AudioConfig = field(default_factory=AudioConfig)
    live: LiveConfig = field(default_factory=LiveConfig)
    receivers: ReceiverConfig = field(default_factory=ReceiverConfig)
    startup: StartupConfig = field(default_factory=StartupConfig)
    default_state: dict[str, Any] = field(default_factory=dict)
    keys: dict[str, str] = field(default_factory=dict)


def default_config() -> KiwiClientConfig:
    """Return the built-in default configuration."""
    return _config_from_dict(tomllib.loads(DEFAULT_CONFIG_TOML))


def load_config(path: str | Path | None = None) -> KiwiClientConfig:
    """Load configuration from TOML, overlaying the built-in defaults."""
    config = default_config()
    if path is None:
        return config
    data = tomllib.loads(Path(path).read_text(encoding="utf-8"))
    return replace(_merge_config(config, data), source_path=str(Path(path)))


def _merge_config(config: KiwiClientConfig, data: dict[str, Any]) -> KiwiClientConfig:
    steps = config.steps
    volume = config.volume
    audio = config.audio
    live = config.live
    receivers = config.receivers
    startup = config.startup
    default_state = dict(config.default_state)
    keys = dict(config.keys)

    if isinstance(data.get("steps"), dict):
        step_data = data["steps"]
        steps = replace(
            steps,
            small_hz=int(step_data.get("small_hz", steps.small_hz)),
            medium_hz=int(step_data.get("medium_hz", steps.medium_hz)),
            large_hz=int(step_data.get("large_hz", steps.large_hz)),
        )
    if isinstance(data.get("volume"), dict):
        volume_data = data["volume"]
        volume = replace(volume, step_percent=int(volume_data.get("step_percent", volume.step_percent)))
    if isinstance(data.get("audio"), dict):
        audio_data = data["audio"]
        audio = replace(
            audio,
            startup_mute_ms=int(audio_data.get("startup_mute_ms", audio.startup_mute_ms)),
            startup_fade_in_ms=int(audio_data.get("startup_fade_in_ms", audio.startup_fade_in_ms)),
            stop_fade_out_ms=int(audio_data.get("stop_fade_out_ms", audio.stop_fade_out_ms)),
        )
    if isinstance(data.get("live"), dict):
        live_data = data["live"]
        live = replace(
            live,
            allow_live=bool(live_data.get("allow_live", live.allow_live)),
            duration_seconds=float(live_data.get("duration_seconds", live.duration_seconds)),
            max_frames=int(live_data.get("max_frames", live.max_frames)),
        )
    if isinstance(data.get("receivers"), dict):
        receiver_data = data["receivers"]
        allowed = receiver_data.get("allowed", receivers.allowed)
        receivers = replace(
            receivers,
            restricted=bool(receiver_data.get("restricted", receivers.restricted)),
            allowed=tuple(str(receiver) for receiver in allowed),
        )
    if isinstance(data.get("startup"), dict):
        startup_data = data["startup"]
        startup = replace(
            startup,
            state_file=str(startup_data.get("state_file", startup.state_file)),
            mode=str(startup_data.get("mode", startup.mode)),
            preset=int(startup_data.get("preset", startup.preset)),
            playback=bool(startup_data.get("playback", startup.playback)),
        )
    if isinstance(data.get("default_state"), dict):
        default_state.update(data["default_state"])
    if isinstance(data.get("keys"), dict):
        keys.update({str(key): str(value) for key, value in data["keys"].items()})

    return KiwiClientConfig(
        source_path=config.source_path,
        steps=steps,
        volume=volume,
        audio=audio,
        live=live,
        receivers=receivers,
        startup=startup,
        default_state=default_state,
        keys=keys,
    )


def add_allowed_receiver_to_config(path: str | Path, receiver: str) -> bool:
    """Add a receiver to `[receivers].allowed` in a TOML config file if missing.

    Returns true when the file was changed. This small writer intentionally only
    rewrites the `allowed = [...]` line inside the existing `[receivers]`
    section, preserving the rest of the local example config.
    """
    path = Path(path)
    text = path.read_text(encoding="utf-8")
    data = tomllib.loads(text)
    receiver_data = data.get("receivers", {}) if isinstance(data.get("receivers"), dict) else {}
    allowed = [str(item) for item in receiver_data.get("allowed", [])]
    if receiver in allowed:
        return False
    allowed.append(receiver)
    new_allowed = "allowed = [" + ", ".join(_toml_string(item) for item in allowed) + "]"
    lines = text.splitlines()
    in_receivers = False
    allowed_line_index: int | None = None
    insert_index: int | None = None
    for index, line in enumerate(lines):
        stripped = line.strip()
        if stripped.startswith("[") and stripped.endswith("]"):
            if in_receivers:
                insert_index = index
                break
            in_receivers = stripped == "[receivers]"
            continue
        if in_receivers and stripped.startswith("allowed") and "=" in stripped:
            allowed_line_index = index
            break
    if allowed_line_index is not None:
        lines[allowed_line_index] = new_allowed
    elif insert_index is not None:
        lines.insert(insert_index, new_allowed)
    else:
        if lines and lines[-1].strip():
            lines.append("")
        if not in_receivers:
            lines.extend(["[receivers]", new_allowed])
        else:
            lines.append(new_allowed)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return True


def _toml_string(value: str) -> str:
    return '"' + value.replace('\\', '\\\\').replace('"', '\\"') + '"'


def _config_from_dict(data: dict[str, Any]) -> KiwiClientConfig:
    return _merge_config(KiwiClientConfig(), data)
