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

[keys]
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
class KiwiClientConfig:
    """Loaded client configuration."""

    steps: StepConfig = field(default_factory=StepConfig)
    volume: VolumeConfig = field(default_factory=VolumeConfig)
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
    return _merge_config(config, data)


def _merge_config(config: KiwiClientConfig, data: dict[str, Any]) -> KiwiClientConfig:
    steps = config.steps
    volume = config.volume
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
    if isinstance(data.get("keys"), dict):
        keys.update({str(key): str(value) for key, value in data["keys"].items()})

    return KiwiClientConfig(steps=steps, volume=volume, keys=keys)


def _config_from_dict(data: dict[str, Any]) -> KiwiClientConfig:
    return _merge_config(KiwiClientConfig(), data)
