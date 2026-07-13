"""Persistence helpers for TUI radio state and presets."""

from __future__ import annotations

import json
import tomllib
from dataclasses import fields
from pathlib import Path
from typing import Any

MINIMAL_PRESET_FIELDS = ("host", "port", "frequency_khz", "mode", "low_cut_hz", "high_cut_hz")
FULL_PRESET_EXCLUDED_FIELDS = frozenset(
    {
        "allowed_receivers",
        "audio_startup_mute_ms",
        "audio_startup_fade_in_ms",
        "audio_stop_fade_out_ms",
        "receivers_restricted",
        "user",
        "volume_percent",
        "duration_seconds",
        "max_frames",
        "cw_offset_hz",
        "mode_step_pairs",
        "mode_step_indices",
        "connected",
    }
)
LAST_STATE_FIELDS = (
    "host",
    "port",
    "frequency_khz",
    "mode",
    "low_cut_hz",
    "high_cut_hz",
    "mode_passbands",
    "mode_step_indices",
    "user",
    "volume_percent",
    "agc_on",
    "agc_hang",
    "agc_threshold",
    "agc_slope",
    "agc_decay_ms",
    "agc_gain",
)


def state_field_names(state: Any) -> tuple[str, ...]:
    return tuple(field.name for field in fields(state))


def minimal_preset(state: Any) -> dict[str, Any]:
    return {field: getattr(state, field) for field in MINIMAL_PRESET_FIELDS}


def full_preset(state: Any) -> dict[str, Any]:
    return {
        field: _json_value(getattr(state, field))
        for field in state_field_names(state)
        if field not in FULL_PRESET_EXCLUDED_FIELDS
    }


def last_state_preset(state: Any) -> dict[str, Any]:
    """Return only ephemeral last-state fields, excluding config-owned settings."""
    return {field: _json_value(getattr(state, field)) for field in LAST_STATE_FIELDS if hasattr(state, field)}


def apply_preset(state: Any, preset: dict[str, Any]) -> Any:
    values = {field: getattr(state, field) for field in state_field_names(state)}
    for key, value in preset.items():
        if key in values:
            values[key] = _state_value(key, value)
    return state.__class__(**values)


def load_state_file(path: str | Path) -> dict[str, Any]:
    """Load ephemeral TUI state. Durable presets live in presets TOML."""
    path = Path(path).expanduser()
    if not path.exists():
        return {"last_state": None}
    data = json.loads(path.read_text(encoding="utf-8"))
    unknown = set(data) - {"last_state"}
    if unknown:
        raise ValueError(f"unsupported state file keys: {', '.join(sorted(unknown))}")
    return {"last_state": data.get("last_state")}


def save_state_file(path: str | Path, *, last_state: Any) -> None:
    """Save ephemeral TUI state only."""
    path = Path(path).expanduser()
    path.parent.mkdir(parents=True, exist_ok=True)
    data = {"last_state": last_state_preset(last_state)}
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def load_presets_file(path: str | Path) -> dict[str, Any]:
    """Load durable radio and receiver presets from TOML."""
    path = Path(path).expanduser()
    if not path.exists():
        return {"presets": {}, "receiver_presets": {}}
    data = tomllib.loads(path.read_text(encoding="utf-8"))
    return {
        "presets": {str(key): value for key, value in data.get("radio_presets", {}).items()},
        "receiver_presets": {str(key): value for key, value in data.get("receiver_presets", {}).items()},
    }


def save_presets_file(
    path: str | Path,
    *,
    presets: dict[Any, dict[str, Any]],
    receiver_presets: dict[Any, dict[str, str]] | None = None,
) -> None:
    """Save durable radio and receiver presets to TOML."""
    path = Path(path).expanduser()
    path.parent.mkdir(parents=True, exist_ok=True)
    lines: list[str] = []
    for key, preset in sorted(presets.items(), key=lambda item: str(item[0])):
        lines.append(f"[radio_presets.{_toml_key(str(key))}]")
        for field, value in sorted(preset.items()):
            lines.append(f"{field} = {_toml_value(value)}")
        lines.append("")
    for key, preset in sorted((receiver_presets or {}).items(), key=lambda item: str(item[0])):
        lines.append(f"[receiver_presets.{_toml_key(str(key))}]")
        for field, value in sorted(preset.items()):
            lines.append(f"{field} = {_toml_value(value)}")
        lines.append("")
    path.write_text("\n".join(lines).rstrip() + ("\n" if lines else ""), encoding="utf-8")


def _toml_key(key: str) -> str:
    if key.replace("_", "").replace("-", "").isalnum() and not key[0].isdigit():
        return key
    return '"' + key.replace('\\', '\\\\').replace('"', '\\"') + '"'


def _toml_value(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return repr(value)
    if isinstance(value, (tuple, list)):
        return "[" + ", ".join(_toml_value(item) for item in value) + "]"
    if isinstance(value, dict):
        return "{ " + ", ".join(f"{_toml_key(str(key))} = {_toml_value(item)}" for key, item in sorted(value.items())) + " }"
    return '"' + str(value).replace('\\', '\\\\').replace('"', '\\"') + '"'


def _json_value(value: Any) -> Any:
    if isinstance(value, tuple):
        return [_json_value(item) for item in value]
    if isinstance(value, dict):
        return {str(key): _json_value(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_json_value(item) for item in value]
    return value


def _state_value(key: str, value: Any) -> Any:
    if key == "allowed_receivers":
        return tuple(value)
    if key == "mode_passbands":
        return {str(mode): (int(cuts[0]), int(cuts[1])) for mode, cuts in dict(value).items()}
    if key == "mode_step_pairs":
        return {str(mode): tuple((float(pair[0]), float(pair[1])) for pair in pairs) for mode, pairs in dict(value).items()}
    if key == "mode_step_indices":
        return {str(mode): int(index) for mode, index in dict(value).items()}
    return value
