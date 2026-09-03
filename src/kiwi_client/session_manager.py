"""UI-neutral interactive radio session state and typed command actions."""

from __future__ import annotations

import math
from dataclasses import dataclass, replace
from typing import TypeAlias

from kiwi_client.commands import encode_modulation, encode_waterfall_view


@dataclass(frozen=True)
class SessionError:
    stream: str
    message: str
    generation: int


@dataclass(frozen=True)
class RadioSessionSnapshot:
    """Immutable desired/active state shared by terminal and future frontends."""

    desired_receiver: str | None = None
    active_receiver: str | None = None
    desired_running: bool = False
    generation: int = 0
    snd_status: str = "idle"
    wf_status: str = "idle"
    error: SessionError | None = None
    frequency_khz: float = 5000.0
    selected_khz: float = 5000.0
    mode: str = "am"
    low_cut_hz: int = -5000
    high_cut_hz: int = 5000
    cw_offset_hz: int = -800
    frequency_decimals: int = 3
    waterfall_center_khz: float = 5000.0
    waterfall_zoom: int = 0
    waterfall_zoom_max: int = 14
    audio_enabled: bool = False

    def __post_init__(self) -> None:
        for name, value in (
            ("frequency_khz", self.frequency_khz),
            ("selected_khz", self.selected_khz),
            ("waterfall_center_khz", self.waterfall_center_khz),
        ):
            if not math.isfinite(value) or value < 0:
                raise ValueError(f"{name} must be a non-negative finite frequency")
        if self.high_cut_hz <= self.low_cut_hz:
            raise ValueError("high_cut_hz must be greater than low_cut_hz")
        if self.frequency_decimals < 0:
            raise ValueError("frequency_decimals must be non-negative")
        if not 0 <= self.waterfall_zoom <= self.waterfall_zoom_max:
            raise ValueError("waterfall zoom must satisfy 0 <= zoom <= zoom_max")


@dataclass(frozen=True)
class SessionCommands:
    snd: tuple[str, ...] = ()
    waterfall: tuple[str, ...] = ()


@dataclass(frozen=True)
class SessionActionResult:
    state: RadioSessionSnapshot
    commands: SessionCommands = SessionCommands()


@dataclass(frozen=True)
class SetSessionIntent:
    running: bool
    receiver: str | None = None


@dataclass(frozen=True)
class TransportUpdate:
    stream: str
    status: str
    generation: int
    error: str | None = None
    active_receiver: str | None = None


@dataclass(frozen=True)
class SelectFrequency:
    frequency_khz: float


@dataclass(frozen=True)
class TuneSelected:
    pass


@dataclass(frozen=True)
class DirectFrequency:
    frequency_khz: float


@dataclass(frozen=True)
class RecenterWaterfall:
    pass


@dataclass(frozen=True)
class ZoomWaterfall:
    delta: int


@dataclass(frozen=True)
class ToggleAudio:
    pass


SessionAction: TypeAlias = (
    SetSessionIntent
    | TransportUpdate
    | SelectFrequency
    | TuneSelected
    | DirectFrequency
    | RecenterWaterfall
    | ZoomWaterfall
    | ToggleAudio
)


def _frequency(value: float) -> float:
    frequency = float(value)
    if not math.isfinite(frequency) or frequency < 0:
        raise ValueError("frequency must be a non-negative finite number in kHz")
    return frequency


def _snd_tune(state: RadioSessionSnapshot, frequency_khz: float) -> str:
    radio_frequency_khz = frequency_khz
    if state.mode.lower() == "cw":
        radio_frequency_khz += state.cw_offset_hz / 1000.0
    return encode_modulation(
        state.mode,
        state.low_cut_hz,
        state.high_cut_hz,
        radio_frequency_khz,
        frequency_decimals=state.frequency_decimals,
    )


def _wf_view(state: RadioSessionSnapshot, frequency_khz: float, zoom: int) -> str:
    return encode_waterfall_view(
        zoom,
        frequency_khz,
        frequency_decimals=state.frequency_decimals,
    )


class RadioSessionManager:
    """Reduce typed UI actions into immutable state and stream commands."""

    def __init__(self, state: RadioSessionSnapshot | None = None) -> None:
        self.state = state or RadioSessionSnapshot()

    def dispatch(self, action: SessionAction) -> SessionActionResult:
        commands = SessionCommands()
        state = self.state

        if isinstance(action, SetSessionIntent):
            generation = state.generation + 1
            receiver = state.desired_receiver if action.receiver is None else action.receiver
            if action.running:
                state = replace(
                    state,
                    desired_receiver=receiver,
                    active_receiver=None,
                    desired_running=True,
                    generation=generation,
                    snd_status="starting",
                    wf_status="waiting",
                    error=None,
                )
            else:
                state = replace(
                    state,
                    desired_running=False,
                    generation=generation,
                    snd_status="stopping" if state.snd_status not in ("idle", "stopped") else "stopped",
                    wf_status="stopping" if state.wf_status not in ("idle", "stopped") else "stopped",
                    error=None,
                )
        elif isinstance(action, TransportUpdate):
            if action.stream not in ("snd", "wf"):
                raise ValueError("transport stream must be 'snd' or 'wf'")
            if action.generation != state.generation:
                return SessionActionResult(state)
            changes = {f"{action.stream}_status": action.status}
            if action.active_receiver is not None:
                changes["active_receiver"] = action.active_receiver
            if action.error is not None:
                changes["error"] = SessionError(action.stream, action.error, action.generation)
            state = replace(state, **changes)
        elif isinstance(action, SelectFrequency):
            state = replace(state, selected_khz=_frequency(action.frequency_khz))
        elif isinstance(action, TuneSelected):
            state = replace(state, frequency_khz=state.selected_khz)
            commands = SessionCommands(snd=(_snd_tune(state, state.frequency_khz),))
        elif isinstance(action, DirectFrequency):
            frequency_khz = _frequency(action.frequency_khz)
            state = replace(
                state,
                frequency_khz=frequency_khz,
                selected_khz=frequency_khz,
                waterfall_center_khz=frequency_khz,
            )
            commands = SessionCommands(
                snd=(_snd_tune(state, frequency_khz),),
                waterfall=(_wf_view(state, frequency_khz, state.waterfall_zoom),),
            )
        elif isinstance(action, RecenterWaterfall):
            state = replace(state, waterfall_center_khz=state.selected_khz)
            commands = SessionCommands(
                waterfall=(_wf_view(state, state.selected_khz, state.waterfall_zoom),),
            )
        elif isinstance(action, ZoomWaterfall):
            zoom = min(max(0, state.waterfall_zoom + action.delta), state.waterfall_zoom_max)
            if zoom != state.waterfall_zoom:
                state = replace(state, waterfall_zoom=zoom, waterfall_center_khz=state.selected_khz)
                commands = SessionCommands(
                    waterfall=(_wf_view(state, state.selected_khz, zoom),),
                )
        elif isinstance(action, ToggleAudio):
            state = replace(state, audio_enabled=not state.audio_enabled)
        else:  # pragma: no cover - defensive against untyped callers
            raise TypeError(f"unsupported session action: {type(action).__name__}")

        self.state = state
        return SessionActionResult(state, commands)
