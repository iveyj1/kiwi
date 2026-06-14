"""Persistence helpers for TUI radio state and presets."""

from __future__ import annotations

import json
from dataclasses import fields
from pathlib import Path
from typing import Any

MINIMAL_PRESET_FIELDS = ("host", "port", "frequency_khz", "mode", "low_cut_hz", "high_cut_hz")


def state_field_names(state: Any) -> tuple[str, ...]:
    return tuple(field.name for field in fields(state))


def minimal_preset(state: Any) -> dict[str, Any]:
    return {field: getattr(state, field) for field in MINIMAL_PRESET_FIELDS}


def full_preset(state: Any) -> dict[str, Any]:
    return {field: _json_value(getattr(state, field)) for field in state_field_names(state)}


def apply_preset(state: Any, preset: dict[str, Any]) -> Any:
    values = {field: getattr(state, field) for field in state_field_names(state)}
    for key, value in preset.items():
        if key in values:
            values[key] = _state_value(key, value)
    return state.__class__(**values)


def load_state_file(path: str | Path) -> dict[str, Any]:
    path = Path(path).expanduser()
    if not path.exists():
        return {"last_state": None, "presets": {}}
    data = json.loads(path.read_text(encoding="utf-8"))
    return {
        "last_state": data.get("last_state"),
        "presets": {str(key): value for key, value in data.get("presets", {}).items()},
    }


def save_state_file(path: str | Path, *, last_state: Any, presets: dict[int, dict[str, Any]]) -> None:
    path = Path(path).expanduser()
    path.parent.mkdir(parents=True, exist_ok=True)
    data = {
        "last_state": full_preset(last_state),
        "presets": {str(key): value for key, value in sorted(presets.items())},
    }
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _json_value(value: Any) -> Any:
    if isinstance(value, tuple):
        return list(value)
    return value


def _state_value(key: str, value: Any) -> Any:
    if key == "allowed_receivers":
        return tuple(value)
    return value
