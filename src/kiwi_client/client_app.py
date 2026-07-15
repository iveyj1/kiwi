"""Basic scriptable KiwiSDR client control surface.

This is the first Milestone 6 client shell. It manages receiver/frequency/mode
state and can print guarded live-operation plans without opening network
connections. Actual play/record/capture operations remain in their dedicated
modules.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import queue
import shlex
from dataclasses import asdict, dataclass, field, replace
from urllib.parse import urlsplit
from pathlib import Path
from threading import Event
from typing import Any, Iterable, Protocol

from kiwi_client.commands import AgcSettings, encode_agc, encode_modulation
from kiwi_client.live_capture import LiveSndCaptureConfig, capture_live_snd
from kiwi_client.live_play import LiveSndPlaybackConfig, play_live_snd
from kiwi_client.live_record import LiveSndWavRecordConfig, record_live_snd_wav
from kiwi_client.live_worker import BackgroundOperation, StatusCallback
from kiwi_client.playback import NullAudioSink, SoundDeviceSink
from kiwi_client.state_store import apply_preset, full_preset, minimal_preset
from kiwi_client.system_volume import SystemVolumeControl, VolumeControl


DEFAULT_MODE_PASSBANDS: dict[str, tuple[int, int]] = {
    "am": (-5000, 5000),
    "usb": (0, 3000),
    "lsb": (-3000, 0),
    "cw": (650, 1050),
}
DEFAULT_LOW_CUT_HZ = DEFAULT_MODE_PASSBANDS["am"][0]
DEFAULT_HIGH_CUT_HZ = DEFAULT_MODE_PASSBANDS["am"][1]
DEFAULT_CW_OFFSET_HZ = -800
DEFAULT_FREQUENCY_COMMAND_DECIMALS = 3
DEFAULT_MODE_STEP_PAIRS: dict[str, tuple[tuple[float, float], ...]] = {
    "am": ((5000, 1000),),
    "usb": ((1000, 100),),
    "lsb": ((1000, 100),),
    "cw": ((100, 10),),
}


@dataclass(frozen=True)
class RadioSessionState:
    """Controller-owned interactive receiver/playback session snapshot."""

    mode: str = "idle"
    desired_receiver: str | None = None
    active_receiver: str | None = None
    desired_playback: bool = False
    operation_name: str | None = None
    error: str | None = None
    generation: int = 0

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ClientState:
    """Interactive client state independent of transport/UI."""

    host: str = "10.0.0.41"
    port: int = 8073
    frequency_khz: float = 5000.0
    mode: str = "am"
    low_cut_hz: int = DEFAULT_LOW_CUT_HZ
    high_cut_hz: int = DEFAULT_HIGH_CUT_HZ
    mode_passbands: dict[str, tuple[int, int]] = field(default_factory=lambda: dict(DEFAULT_MODE_PASSBANDS))
    cw_offset_hz: int = DEFAULT_CW_OFFSET_HZ
    frequency_command_decimals: int = DEFAULT_FREQUENCY_COMMAND_DECIMALS
    mode_step_pairs: dict[str, tuple[tuple[float, float], ...]] = field(default_factory=lambda: dict(DEFAULT_MODE_STEP_PAIRS))
    mode_step_indices: dict[str, int] = field(default_factory=dict)
    user: str = "kiwi-client"
    duration_seconds: float = 60.0
    max_frames: int = 1500
    volume_percent: int = 10
    audio_startup_mute_ms: int = 300
    audio_startup_fade_in_ms: int = 100
    audio_stop_fade_out_ms: int = 100
    agc_on: bool = True
    agc_hang: bool = False
    agc_threshold: int = -100
    agc_slope: int = 6
    agc_decay_ms: int = 1000
    agc_gain: int = 50
    receivers_restricted: bool = True
    allowed_receivers: tuple[str, ...] = ("10.0.0.40:8073", "10.0.0.41:8073")
    connected: bool = False

    @property
    def receiver(self) -> str:
        return f"{self.host}:{self.port}"

    @property
    def current_step_pair(self) -> tuple[float, float]:
        pairs = self.mode_step_pairs.get(self.mode.lower()) or DEFAULT_MODE_STEP_PAIRS.get(self.mode.lower()) or ((1000, 100),)
        index = max(0, min(self.mode_step_indices.get(self.mode.lower(), 0), len(pairs) - 1))
        return float(pairs[index][0]), float(pairs[index][1])

    @property
    def current_step_hz(self) -> float:
        return self.current_step_pair[0]

    @property
    def current_small_step_hz(self) -> float:
        return self.current_step_pair[1]

    @property
    def radio_frequency_khz(self) -> float:
        if self.mode.lower() == "cw":
            return self.frequency_khz + self.cw_offset_hz / 1000.0
        return self.frequency_khz

    def as_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["receiver"] = self.receiver
        data["radio_frequency_khz"] = self.radio_frequency_khz
        data["current_step_hz"] = self.current_step_hz
        data["current_small_step_hz"] = self.current_small_step_hz
        return data


class ClientCommandError(ValueError):
    """Raised for invalid client shell commands."""


def normalized_mode(mode: str) -> str:
    return mode.lower()


def passband_for_mode(state: ClientState, mode: str) -> tuple[int, int]:
    mode = normalized_mode(mode)
    if mode in state.mode_passbands:
        low, high = state.mode_passbands[mode]
        return int(low), int(high)
    return DEFAULT_MODE_PASSBANDS.get(mode, (state.low_cut_hz, state.high_cut_hz))


def set_mode_passband(state: ClientState, mode: str, low_cut_hz: int, high_cut_hz: int) -> ClientState:
    mode = normalized_mode(mode)
    passbands = dict(state.mode_passbands)
    passbands[mode] = (int(low_cut_hz), int(high_cut_hz))
    active_low, active_high = (int(low_cut_hz), int(high_cut_hz)) if normalized_mode(state.mode) == mode else (state.low_cut_hz, state.high_cut_hz)
    return replace(state, mode_passbands=passbands, low_cut_hz=active_low, high_cut_hz=active_high)


def switch_mode(state: ClientState, mode: str, passband: tuple[int, int] | None = None) -> ClientState:
    mode = normalized_mode(mode)
    passbands = dict(state.mode_passbands)
    if passband is not None:
        passbands[mode] = (int(passband[0]), int(passband[1]))
    low, high = passbands.get(mode, DEFAULT_MODE_PASSBANDS.get(mode, (state.low_cut_hz, state.high_cut_hz)))
    return replace(state, mode=mode, low_cut_hz=int(low), high_cut_hz=int(high), mode_passbands=passbands)


def step_pair_index(state: ClientState, mode: str) -> int:
    mode = normalized_mode(mode)
    pairs = state.mode_step_pairs.get(mode) or DEFAULT_MODE_STEP_PAIRS.get(mode) or ((1000, 100),)
    return max(0, min(state.mode_step_indices.get(mode, 0), len(pairs) - 1))


def step_mode_pair(state: ClientState, mode: str, delta: int) -> ClientState:
    mode = normalized_mode(mode)
    pairs = state.mode_step_pairs.get(mode) or DEFAULT_MODE_STEP_PAIRS.get(mode) or ((1000, 100),)
    index = max(0, min(step_pair_index(state, mode) + delta, len(pairs) - 1))
    return replace(state, mode_step_indices={**state.mode_step_indices, mode: index})


class ClientOperations(Protocol):
    """Executable operations used by the client controller."""

    def play(
        self,
        config: LiveSndPlaybackConfig,
        *,
        null_sink: bool,
        stop_event: Event | None = None,
        command_queue: queue.Queue[str] | None = None,
        status_callback: StatusCallback | None = None,
    ) -> dict[str, Any]: ...

    def record(
        self,
        config: LiveSndWavRecordConfig,
        *,
        stop_event: Event | None = None,
        status_callback: StatusCallback | None = None,
    ) -> dict[str, Any]: ...

    def capture(
        self,
        config: LiveSndCaptureConfig,
        *,
        stop_event: Event | None = None,
        status_callback: StatusCallback | None = None,
    ) -> dict[str, Any]: ...


class LiveClientOperations:
    """Default operations that call guarded live play/record/capture modules."""

    def play(
        self,
        config: LiveSndPlaybackConfig,
        *,
        null_sink: bool,
        stop_event: Event | None = None,
        command_queue: queue.Queue[str] | None = None,
        status_callback: StatusCallback | None = None,
    ) -> dict[str, Any]:
        sink = NullAudioSink() if null_sink else SoundDeviceSink()
        result = asyncio.run(
            play_live_snd(
                config,
                sink,
                allow_live=True,
                dry_run=null_sink,
                stop_event=stop_event,
                command_queue=command_queue,
                status_callback=status_callback,
            )
        )
        data = asdict(result)
        data["path"] = str(result.path)
        return data

    def record(
        self,
        config: LiveSndWavRecordConfig,
        *,
        stop_event: Event | None = None,
        status_callback: StatusCallback | None = None,
    ) -> dict[str, Any]:
        result = asyncio.run(
            record_live_snd_wav(config, allow_live=True, stop_event=stop_event, status_callback=status_callback)
        )
        data = asdict(result)
        data["path"] = str(result.path)
        return data

    def capture(
        self,
        config: LiveSndCaptureConfig,
        *,
        stop_event: Event | None = None,
        status_callback: StatusCallback | None = None,
    ) -> dict[str, Any]:
        path = asyncio.run(capture_live_snd(config, allow_live=True, stop_event=stop_event, status_callback=status_callback))
        return {"path": str(path)}


class ClientController:
    """Apply simple user commands to client state and produce plans."""

    def __init__(
        self,
        state: ClientState | None = None,
        operations: ClientOperations | None = None,
        background: BackgroundOperation | None = None,
        allow_live_default: bool = False,
        volume_control: VolumeControl | None = None,
        presets: dict[int, dict[str, Any]] | None = None,
        receiver_presets: dict[Any, dict[str, str]] | None = None,
    ) -> None:
        self.state = state or ClientState()
        self.operations = operations or LiveClientOperations()
        self.background = background or BackgroundOperation()
        self.allow_live_default = allow_live_default
        self.volume_control = volume_control or SystemVolumeControl()
        self.presets: dict[Any, dict[str, Any]] = dict(presets or {})
        self.receiver_presets: dict[Any, dict[str, str]] = dict(receiver_presets or {})
        self.last_play_bg_null_sink = False
        self.session = RadioSessionState(desired_receiver=self.state.receiver)
        self.running = True

    def execute(self, line: str) -> dict[str, Any] | None:
        """Execute one shell command entry and return a JSON-serializable response."""
        commands = split_command_entry(line)
        if not commands:
            return None
        if len(commands) == 1:
            return self._execute_one(commands[0])
        return self._execute_batch(commands)

    def _execute_batch(self, commands: list[str]) -> dict[str, Any]:
        if all(is_atomic_state_command(command) for command in commands):
            return self._execute_atomic_state_batch(commands)
        responses: list[dict[str, Any]] = []
        for command in commands:
            response = self._execute_one(command)
            if response is not None:
                responses.append(response)
            if not self.running:
                break
        return {"type": "batch", "responses": responses}

    def _execute_atomic_state_batch(self, commands: list[str]) -> dict[str, Any]:
        trial = ClientController(
            state=self.state,
            operations=self.operations,
            allow_live_default=self.allow_live_default,
            volume_control=self.volume_control,
            presets=self.presets,
            receiver_presets=self.receiver_presets,
        )
        responses: list[dict[str, Any]] = []
        touched_modulation = False
        touched_agc = False
        for command_line in commands:
            command = normalized_command_name(command_line)
            response = trial._execute_one(command_line)
            if response is not None:
                responses.append(response)
            if command in MODULATION_STATE_COMMANDS:
                touched_modulation = True
            if command == "agc" and len(shlex.split(command_line)) > 1:
                touched_agc = True
        self.state = trial.state
        self.presets = dict(trial.presets)
        self.receiver_presets = dict(trial.receiver_presets)
        active_commands: list[str] = []
        if touched_modulation:
            active_commands.append(
                self._modulation_command()
            )
        if touched_agc:
            active_commands.append(self._agc_command())
        active_operation: dict[str, Any] | None = None
        for active_command in active_commands:
            current_status = self.background.status()
            if not current_status.running or current_status.name != "play":
                active_operation = None
                continue
            try:
                active_operation = self.background.send_command(active_command).as_dict()
            except RuntimeError:
                active_operation = None
        result: dict[str, Any] = {"type": "batch", "responses": responses, "state": self.state.as_dict()}
        if active_commands and active_operation is not None:
            result["active_commands"] = active_commands
            result["operation"] = active_operation
        return result

    def _execute_one(self, stripped: str) -> dict[str, Any] | None:
        """Execute one parsed shell command and return a JSON-serializable response."""
        if not stripped or stripped.startswith("#"):
            return None
        parts = shlex.split(stripped)
        command = command_aliases().get(parts[0].lower(), parts[0].lower())
        args = parts[1:]

        if command in {"quit", "exit"}:
            self.running = False
            return {"type": "quit"}
        if command == "help":
            return {"type": "help", "commands": available_commands()}
        if command == "status":
            return {"type": "status", "state": self._state_dict_with_connection(), "session": self.session_status().as_dict()}
        if command == "connect":
            self.state = replace(self.state, connected=True)
            return {"type": "state", "state": self.state.as_dict()}
        if command == "disconnect":
            self.state = replace(self.state, connected=False)
            return {"type": "state", "state": self.state.as_dict()}
        if command == "receiver":
            self._require_arg_count(args, 1, "receiver <host>[:port]")
            return self._set_receiver_response(args[0])
        if command == "add-receiver":
            return self._handle_add_receiver(args)
        if command == "tune":
            self._require_arg_count(args, 1, "tune <frequency_khz>")
            self.state = replace(self.state, frequency_khz=float(args[0]))
            return self._state_response()
        if command == "mode":
            if len(args) not in {1, 3}:
                raise ClientCommandError("usage: mode <mode> [low_cut_hz high_cut_hz]")
            mode = args[0].lower()
            if len(args) == 3:
                self.state = switch_mode(self.state, mode, (int(args[1]), int(args[2])))
            else:
                self.state = switch_mode(self.state, mode)
            return self._state_response()
        if command == "filter":
            self._require_arg_count(args, 2, "filter <low_cut_hz> <high_cut_hz>")
            self.state = set_mode_passband(self.state, self.state.mode, int(args[0]), int(args[1]))
            return self._state_response()
        if command == "tune-step":
            self._require_arg_count(args, 1, "tune-step <+/-hz|small|medium|large>")
            delta_hz = self._parse_tune_step_hz(args[0])
            self.state = replace(self.state, frequency_khz=self.state.frequency_khz + delta_hz / 1000.0)
            return self._state_response()
        if command == "step-pair":
            self._require_arg_count(args, 1, "step-pair <+/-n>")
            self.state = step_mode_pair(self.state, self.state.mode, int(args[0]))
            return {"type": "state", "state": self.state.as_dict()}
        if command == "volume":
            self._require_arg_count(args, 1, "volume <percent>")
            return self._set_volume(self._clamp_volume(int(args[0])))
        if command == "volume-step":
            self._require_arg_count(args, 1, "volume-step <delta_percent>")
            return self._set_volume(self._clamp_volume(self._current_volume_percent() + int(args[0])))
        if command == "agc":
            return self._handle_agc(args)
        if command == "store":
            return self._handle_store(args)
        if command == "recall":
            self._require_arg_count(args, 1, "recall <n>")
            return self._recall_preset(args[0])
        if command == "duration":
            self._require_arg_count(args, 1, "duration <seconds>")
            self.state = replace(self.state, duration_seconds=float(args[0]))
            return {"type": "state", "state": self.state.as_dict()}
        if command == "frames":
            self._require_arg_count(args, 1, "frames <max_snd_frames>")
            self.state = replace(self.state, max_frames=int(args[0]))
            return {"type": "state", "state": self.state.as_dict()}
        if command == "dashboard":
            from kiwi_client.tui import render_dashboard

            return {"type": "dashboard", "text": render_dashboard(self.state)}
        if command == "play-plan":
            self._require_arg_count(args, 0, "play-plan")
            return {"type": "play-plan", "plan": self._playback_config().dry_run_plan()}
        if command == "record-plan":
            self._require_arg_count(args, 1, "record-plan <output.wav>")
            return {"type": "record-plan", "plan": self._record_config(Path(args[0])).dry_run_plan()}
        if command == "capture-plan":
            self._require_arg_count(args, 1, "capture-plan <output.jsonl>")
            return {"type": "capture-plan", "plan": self._capture_config(Path(args[0])).dry_run_plan()}
        if command == "play":
            positional, flags = self._parse_flags(args, {"--allow-live", "--null-sink"})
            self._require_arg_count(positional, 0, "play --allow-live [--null-sink]")
            self._require_allow_live(flags, "play-plan")
            return {"type": "play", "result": self.operations.play(self._playback_config(), null_sink="--null-sink" in flags)}
        if command == "play-bg":
            positional, flags = self._parse_flags(args, {"--allow-live", "--null-sink"})
            self._require_arg_count(positional, 0, "play-bg --allow-live [--null-sink]")
            self._require_allow_live(flags, "play-plan")
            return self._start_playback_background("--null-sink" in flags)
        if command == "stop":
            return self._stop_background()
        if command == "wait":
            if len(args) > 1:
                raise ClientCommandError("usage: wait [seconds]")
            timeout = float(args[0]) if args else None
            return self._wait_background(timeout)
        if command == "operation-status":
            return {"type": "operation-status", "operation": self.background.status().as_dict(), "session": self.session_status().as_dict()}
        if command == "record":
            positional, flags = self._parse_flags(args, {"--allow-live", "--overwrite"})
            self._require_arg_count(positional, 1, "record <output.wav> --allow-live [--overwrite]")
            self._require_allow_live(flags, "record-plan <output.wav>")
            return {
                "type": "record",
                "result": self.operations.record(self._record_config(Path(positional[0]), overwrite="--overwrite" in flags)),
            }
        if command == "record-bg":
            positional, flags = self._parse_flags(args, {"--allow-live", "--overwrite"})
            self._require_arg_count(positional, 1, "record-bg <output.wav> --allow-live [--overwrite]")
            self._require_allow_live(flags, "record-plan <output.wav>")
            config = self._record_config(Path(positional[0]), overwrite="--overwrite" in flags)
            self.session = replace(self.session, mode="idle", active_receiver=None, desired_playback=False, error=None)
            status = self.background.start(
                "record",
                lambda stop_event, command_queue, status_callback: self.operations.record(
                    config,
                    stop_event=stop_event,
                    status_callback=status_callback,
                ),
            )
            return {"type": "operation-status", "operation": status.as_dict()}
        if command == "capture":
            positional, flags = self._parse_flags(args, {"--allow-live", "--overwrite"})
            self._require_arg_count(positional, 1, "capture <output.jsonl> --allow-live [--overwrite]")
            self._require_allow_live(flags, "capture-plan <output.jsonl>")
            return {
                "type": "capture",
                "result": self.operations.capture(self._capture_config(Path(positional[0]), overwrite="--overwrite" in flags)),
            }
        if command == "capture-bg":
            positional, flags = self._parse_flags(args, {"--allow-live", "--overwrite"})
            self._require_arg_count(positional, 1, "capture-bg <output.jsonl> --allow-live [--overwrite]")
            self._require_allow_live(flags, "capture-plan <output.jsonl>")
            config = self._capture_config(Path(positional[0]), overwrite="--overwrite" in flags)
            self.session = replace(self.session, mode="idle", active_receiver=None, desired_playback=False, error=None)
            status = self.background.start(
                "capture",
                lambda stop_event, command_queue, status_callback: self.operations.capture(
                    config,
                    stop_event=stop_event,
                    status_callback=status_callback,
                ),
            )
            return {"type": "operation-status", "operation": status.as_dict()}
        raise ClientCommandError(f"unknown command: {command}")

    def _state_dict_with_connection(self) -> dict[str, Any]:
        state = self.state.as_dict()
        state["connected"] = bool(self.state.connected or self.background.status().running)
        return state

    def session_status(self) -> RadioSessionState:
        """Return a session snapshot derived from controller intent and worker status."""
        status = self.background.status()
        if status.name == "play" and self.session.desired_playback:
            if status.running:
                mode = "stopping" if status.stop_requested else "playing"
                return replace(
                    self.session,
                    mode=mode,
                    desired_receiver=self.state.receiver,
                    operation_name=status.name,
                    error=None,
                )
            if status.error:
                return replace(
                    self.session,
                    mode="failed",
                    desired_receiver=self.state.receiver,
                    active_receiver=None,
                    operation_name=status.name,
                    error=status.error,
                )
        return replace(
            self.session,
            mode="idle" if not self.session.desired_playback else self.session.mode,
            desired_receiver=self.state.receiver,
            operation_name=status.name,
            error=status.error if status.name == "play" and status.error else None,
        )

    def switch_receiver(
        self,
        receiver: str,
        *,
        preserve_playback: bool = True,
        join_timeout: float = 2.0,
        startup_grace_seconds: float = 0.1,
    ) -> tuple[dict[str, Any] | None, str | None]:
        """Switch receiver, preserving/recovering playback intent when appropriate."""
        status = self.background.status()
        should_start_after_failed = (
            preserve_playback
            and status.name == "play"
            and bool(status.error)
            and not status.running
            and self.session.desired_playback
        )
        if should_start_after_failed:
            state_response = self._set_receiver_response(receiver)
            start_response = self._start_playback_background(self.last_play_bg_null_sink)
            return {"type": "batch", "responses": [state_response, start_response], "session": self.session_status().as_dict()}, f"Receiver: {self.state.receiver}; started playback"

        if not preserve_playback or not status.running or status.name != "play":
            response = self._set_receiver_response(receiver)
            return response, f"Receiver: {self.state.receiver}"

        previous_receiver = self.state.receiver
        null_sink = self.last_play_bg_null_sink
        self.session = replace(self.session, mode="switching", desired_receiver=receiver, error=None)
        self.background.stop()
        stopped = self.background.join(timeout=join_timeout)
        if stopped.running:
            self.session = replace(self.session, mode="stopping", error=None)
            return {"type": "operation-status", "operation": stopped.as_dict(), "session": self.session_status().as_dict()}, "Stopping playback before receiver switch..."

        state_response = self._set_receiver_response(receiver)
        start_response = self._start_playback_background(null_sink)
        startup_status = self.background.join(timeout=startup_grace_seconds)
        if startup_status.error and not startup_status.running:
            error = startup_status.error
            self._set_receiver_response(previous_receiver)
            restore_response = self._start_playback_background(null_sink)
            return (
                {
                    "type": "operation-status",
                    "operation": startup_status.as_dict(),
                    "restore": restore_response,
                    "session": self.session_status().as_dict(),
                },
                f"Receiver switch failed: {error}; restored receiver: {previous_receiver}",
            )
        return {"type": "batch", "responses": [state_response, start_response], "session": self.session_status().as_dict()}, f"Receiver: {self.state.receiver}; restarted playback"

    def _with_receiver(self, value: str) -> ClientState:
        host, port = normalize_receiver_address(value, default_port=self.state.port)
        return replace(self.state, host=host, port=port)

    def _set_receiver_response(self, value: str) -> dict[str, Any]:
        self.state = self._with_receiver(value)
        self.session = replace(self.session, desired_receiver=self.state.receiver)
        return {"type": "state", "state": self.state.as_dict(), "session": self.session_status().as_dict()}

    def _start_playback_background(self, null_sink: bool) -> dict[str, Any]:
        config = self._playback_config()
        self.last_play_bg_null_sink = null_sink
        self.session = replace(
            self.session,
            mode="starting",
            desired_receiver=self.state.receiver,
            active_receiver=self.state.receiver,
            desired_playback=True,
            operation_name="play",
            error=None,
            generation=self.session.generation + 1,
        )
        status = self.background.start(
            "play",
            lambda stop_event, command_queue, status_callback: self.operations.play(
                config,
                null_sink=null_sink,
                stop_event=stop_event,
                command_queue=command_queue,
                status_callback=status_callback,
            ),
        )
        return {"type": "operation-status", "operation": status.as_dict(), "session": self.session_status().as_dict()}

    def _stop_background(self) -> dict[str, Any]:
        status = self.background.stop()
        if status.name == "play":
            self.session = replace(self.session, mode="stopping", desired_playback=False, error=None)
        return {"type": "operation-status", "operation": status.as_dict(), "session": self.session_status().as_dict()}

    def _wait_background(self, timeout: float | None) -> dict[str, Any]:
        status = self.background.join(timeout=timeout)
        if status.name == "play" and not status.running:
            if status.error:
                self.session = replace(self.session, mode="failed", active_receiver=None, error=status.error)
            else:
                self.session = replace(self.session, mode="idle", active_receiver=None, desired_playback=False, error=None)
        return {"type": "operation-status", "operation": status.as_dict(), "session": self.session_status().as_dict()}

    def _modulation_command(self) -> str:
        return encode_modulation(
            self.state.mode,
            self.state.low_cut_hz,
            self.state.high_cut_hz,
            self.state.radio_frequency_khz,
            frequency_decimals=self.state.frequency_command_decimals,
        )

    def _state_response(self) -> dict[str, Any]:
        command = self._modulation_command()
        return self._state_response_with_active_command(command)

    def _state_response_with_active_command(self, command: str) -> dict[str, Any]:
        response: dict[str, Any] = {"type": "state", "state": self.state.as_dict()}
        current_status = self.background.status()
        if not current_status.running or current_status.name != "play":
            return response
        try:
            status = self.background.send_command(command)
        except RuntimeError:
            return response
        response["active_command"] = command
        response["operation"] = status.as_dict()
        return response

    def _handle_add_receiver(self, args: list[str]) -> dict[str, Any]:
        if len(args) < 3:
            raise ClientCommandError("usage: add-receiver <receiver-register> <ip/url[:port]> <description>")
        register = parse_register_id(args[0])
        host, port = normalize_receiver_address(args[1], default_port=8073)
        receiver = f"{host}:{port}"
        description = " ".join(args[2:]).strip()
        if not description:
            raise ClientCommandError("usage: add-receiver <receiver-register> <ip/url[:port]> <description>")
        self.receiver_presets[register] = {"receiver": receiver, "description": description}
        return {
            "type": "receiver-preset",
            "register": register,
            "receiver": receiver,
            "description": description,
        }

    def _handle_store(self, args: list[str]) -> dict[str, Any]:
        if len(args) == 1:
            preset_id = parse_register_id(args[0])
            self.presets[preset_id] = minimal_preset(self.state)
            return {"type": "preset", "preset": preset_id, "scope": "minimal", "state": self.state.as_dict()}
        if len(args) == 2 and args[0].lower() == "all":
            preset_id = parse_register_id(args[1])
            self.presets[preset_id] = full_preset(self.state)
            return {"type": "preset", "preset": preset_id, "scope": "all", "state": self.state.as_dict()}
        raise ClientCommandError("usage: store <n> | store all <n>")

    def _recall_preset(self, preset_id: Any) -> dict[str, Any]:
        preset_id = parse_register_id(str(preset_id))
        if preset_id not in self.presets:
            raise ClientCommandError(f"unknown preset: {preset_id}")
        self.state = apply_preset(self.state, self.presets[preset_id])
        response = self._state_response()
        response["preset"] = preset_id
        return response

    def _current_volume_percent(self) -> int:
        try:
            return self.volume_control.get_percent()
        except RuntimeError:
            return self.state.volume_percent

    def _set_volume(self, percent: int) -> dict[str, Any]:
        self.state = replace(self.state, volume_percent=percent)
        try:
            volume_result = self.volume_control.set_percent(percent)
        except RuntimeError as exc:
            raise ClientCommandError(str(exc)) from exc
        return {"type": "state", "state": self.state.as_dict(), "volume": volume_result}

    def _handle_agc(self, args: list[str]) -> dict[str, Any]:
        if not args:
            return {"type": "state", "state": self.state.as_dict(), "agc_command": self._agc_command()}
        subcommand = args[0].lower()
        if subcommand in {"on", "off"}:
            self._require_arg_count(args, 1, "agc on|off")
            self.state = replace(self.state, agc_on=subcommand == "on")
        elif subcommand == "hang":
            self._require_arg_count(args, 2, "agc hang on|off")
            self.state = replace(self.state, agc_hang=self._parse_on_off(args[1]))
        elif subcommand in {"threshold", "thresh"}:
            self._require_arg_count(args, 2, "agc threshold <value>")
            self.state = replace(self.state, agc_threshold=int(args[1]))
        elif subcommand == "slope":
            self._require_arg_count(args, 2, "agc slope <value>")
            self.state = replace(self.state, agc_slope=int(args[1]))
        elif subcommand in {"decay", "decay-ms"}:
            self._require_arg_count(args, 2, "agc decay <ms>")
            self.state = replace(self.state, agc_decay_ms=int(args[1]))
        elif subcommand in {"gain", "manual-gain", "mangain"}:
            self._require_arg_count(args, 2, "agc gain <value>")
            self.state = replace(self.state, agc_gain=int(args[1]))
        elif subcommand == "set":
            self.state = self._apply_agc_key_values(args[1:])
        else:
            raise ClientCommandError(
                "usage: agc [on|off|hang on|off|threshold <value>|slope <value>|decay <ms>|gain <value>|set key=value ...]"
            )
        agc_command = self._agc_command()
        response = self._state_response_with_active_command(agc_command)
        response["agc_command"] = agc_command
        return response

    def _agc_settings(self) -> AgcSettings:
        return AgcSettings(
            on=self.state.agc_on,
            hang=self.state.agc_hang,
            thresh=self.state.agc_threshold,
            slope=self.state.agc_slope,
            decay=self.state.agc_decay_ms,
            gain=self.state.agc_gain,
        )

    def _agc_command(self) -> str:
        return encode_agc(self._agc_settings())

    def _apply_agc_key_values(self, pairs: list[str]) -> ClientState:
        state = self.state
        if not pairs:
            raise ClientCommandError("usage: agc set key=value ...")
        for pair in pairs:
            if "=" not in pair:
                raise ClientCommandError("usage: agc set key=value ...")
            key, value = pair.split("=", 1)
            key = key.lower().replace("_", "-")
            if key == "on":
                state = replace(state, agc_on=self._parse_bool(value))
            elif key == "hang":
                state = replace(state, agc_hang=self._parse_bool(value))
            elif key in {"threshold", "thresh"}:
                state = replace(state, agc_threshold=int(value))
            elif key == "slope":
                state = replace(state, agc_slope=int(value))
            elif key in {"decay", "decay-ms"}:
                state = replace(state, agc_decay_ms=int(value))
            elif key in {"gain", "manual-gain", "mangain"}:
                state = replace(state, agc_gain=int(value))
            else:
                raise ClientCommandError(f"unknown AGC setting: {key}")
        return state

    @staticmethod
    def _parse_on_off(value: str) -> bool:
        if value.lower() == "on":
            return True
        if value.lower() == "off":
            return False
        raise ClientCommandError("expected on or off")

    @staticmethod
    def _parse_bool(value: str) -> bool:
        if value.lower() in {"1", "true", "yes", "on"}:
            return True
        if value.lower() in {"0", "false", "no", "off"}:
            return False
        raise ClientCommandError("expected boolean value")

    @staticmethod
    def _parse_tune_step_hz(value: str) -> float:
        sign = 1
        token = value.strip().lower()
        if token.startswith("+"):
            token = token[1:]
        elif token.startswith("-"):
            token = token[1:]
            sign = -1
        named = {"small": 100, "medium": 1000, "large": 5000}
        hz = named[token] if token in named else float(token)
        return sign * hz

    @staticmethod
    def _clamp_volume(value: int) -> int:
        return max(0, min(200, value))

    @staticmethod
    def _require_arg_count(args: list[str], count: int, usage: str) -> None:
        if len(args) != count:
            raise ClientCommandError(f"usage: {usage}")

    @staticmethod
    def _parse_flags(args: list[str], allowed: set[str]) -> tuple[list[str], set[str]]:
        positional: list[str] = []
        flags: set[str] = set()
        for arg in args:
            if arg.startswith("--"):
                if arg not in allowed:
                    raise ClientCommandError(f"unsupported flag: {arg}")
                flags.add(arg)
            else:
                positional.append(arg)
        return positional, flags

    def _require_allow_live(self, flags: set[str], plan_command: str) -> None:
        if "--allow-live" not in flags and not self.allow_live_default:
            raise ClientCommandError(
                "refusing live operation without --allow-live; "
                f"inspect with `{plan_command}` first, or set [live] allow_live = true in the TUI config"
            )

    def _playback_config(self) -> LiveSndPlaybackConfig:
        return LiveSndPlaybackConfig(
            host=self.state.host,
            port=self.state.port,
            user=self.state.user,
            frequency_khz=self.state.frequency_khz,
            radio_frequency_khz=self.state.radio_frequency_khz,
            frequency_decimals=self.state.frequency_command_decimals,
            mode=self.state.mode,
            low_cut_hz=self.state.low_cut_hz,
            high_cut_hz=self.state.high_cut_hz,
            duration_seconds=self.state.duration_seconds,
            max_frames=self.state.max_frames,
            startup_mute_ms=self.state.audio_startup_mute_ms,
            startup_fade_in_ms=self.state.audio_startup_fade_in_ms,
            stop_fade_out_ms=self.state.audio_stop_fade_out_ms,
            receivers_restricted=self.state.receivers_restricted,
            allowed_receivers=self.state.allowed_receivers,
        )

    def _record_config(self, output: Path, *, overwrite: bool = False) -> LiveSndWavRecordConfig:
        return LiveSndWavRecordConfig(
            host=self.state.host,
            port=self.state.port,
            output=output,
            user=self.state.user,
            frequency_khz=self.state.frequency_khz,
            radio_frequency_khz=self.state.radio_frequency_khz,
            frequency_decimals=self.state.frequency_command_decimals,
            mode=self.state.mode,
            low_cut_hz=self.state.low_cut_hz,
            high_cut_hz=self.state.high_cut_hz,
            duration_seconds=self.state.duration_seconds,
            max_frames=self.state.max_frames,
            overwrite=overwrite,
            receivers_restricted=self.state.receivers_restricted,
            allowed_receivers=self.state.allowed_receivers,
        )

    def _capture_config(self, output: Path, *, overwrite: bool = False) -> LiveSndCaptureConfig:
        return LiveSndCaptureConfig(
            host=self.state.host,
            port=self.state.port,
            output=output,
            user=self.state.user,
            frequency_khz=self.state.frequency_khz,
            radio_frequency_khz=self.state.radio_frequency_khz,
            frequency_decimals=self.state.frequency_command_decimals,
            mode=self.state.mode,
            low_cut_hz=self.state.low_cut_hz,
            high_cut_hz=self.state.high_cut_hz,
            duration_seconds=self.state.duration_seconds,
            max_frames=self.state.max_frames,
            overwrite=overwrite,
            receivers_restricted=self.state.receivers_restricted,
            allowed_receivers=self.state.allowed_receivers,
        )


ATOMIC_STATE_COMMANDS = {
    "receiver",
    "tune",
    "mode",
    "filter",
    "tune-step",
    "step-pair",
    "agc",
    "duration",
    "frames",
    "recall",
}

MODULATION_STATE_COMMANDS = {"receiver", "tune", "mode", "filter", "tune-step", "recall"}
REGISTER_KEYS = "0123456789abcdefghijklmnopqrstuvwxyz"


def parse_register_id(value: str) -> int | str:
    """Parse one preset register id, preserving digit compatibility."""
    token = value.strip().lower()
    if len(token) != 1 or token not in REGISTER_KEYS:
        raise ClientCommandError("register must be [0..9] or [a..z]")
    return int(token) if token.isdigit() else token


def normalize_receiver_address(value: str, *, default_port: int = 8073) -> tuple[str, int]:
    """Normalize host[:port] or URL-ish receiver addresses."""
    raw = value.strip()
    if not raw:
        raise ClientCommandError("receiver must not be empty")
    if "://" in raw:
        parsed = urlsplit(raw)
        host = parsed.hostname or ""
        try:
            port = parsed.port or default_port
        except ValueError as exc:
            raise ClientCommandError(f"invalid receiver port: {raw}") from exc
    else:
        host_port = raw.split("/", 1)[0]
        if ":" in host_port:
            host, port_text = host_port.rsplit(":", 1)
            try:
                port = int(port_text)
            except ValueError as exc:
                raise ClientCommandError(f"invalid receiver port: {raw}") from exc
        else:
            host = host_port
            port = default_port
    host = host.strip("[]")
    if not host:
        raise ClientCommandError(f"invalid receiver address: {raw}")
    return host, port


def split_command_entry(line: str) -> list[str]:
    """Split a command entry on semicolons outside quotes."""
    commands: list[str] = []
    current: list[str] = []
    quote: str | None = None
    escaped = False
    for char in line:
        if escaped:
            current.append(char)
            escaped = False
            continue
        if char == "\\" and quote != "'":
            current.append(char)
            escaped = True
            continue
        if char in {"'", '"'}:
            if quote is None:
                quote = char
            elif quote == char:
                quote = None
            current.append(char)
            continue
        if char == ";" and quote is None:
            command = "".join(current).strip()
            if command and not command.startswith("#"):
                commands.append(command)
            current = []
            continue
        current.append(char)
    command = "".join(current).strip()
    if command and not command.startswith("#"):
        commands.append(command)
    return commands


def normalized_command_name(command_line: str) -> str:
    """Return the canonical command name for a single command line."""
    parts = shlex.split(command_line)
    if not parts:
        return ""
    return command_aliases().get(parts[0].lower(), parts[0].lower())


def is_atomic_state_command(command_line: str) -> bool:
    """Return true if a command can be validated before mutating live state."""
    return normalized_command_name(command_line) in ATOMIC_STATE_COMMANDS


def command_aliases() -> dict[str, str]:
    """Return short command aliases for interactive use."""
    return {
        "?": "status",
        "re": "receiver",
        "tu": "tune",
        "mo": "mode",
        "fi": "filter",
        "ag": "agc",
        "ad": "add-receiver",
        "stp": "store",
        "rc": "recall",
        "du": "duration",
        "fr": "frames",
        "pb": "play-bg",
        "rb": "record-bg",
        "cb": "capture-bg",
        "sp": "stop",
        "he": "help",
        "q": "quit",
        "qu": "quit",
    }


def available_commands() -> list[str]:
    return [
        "status",
        "connect",
        "disconnect",
        "receiver <host>[:port]",
        "add-receiver <receiver-register> <ip/url[:port]> <description>",
        "tune <frequency_khz>",
        "mode <mode> [low_cut_hz high_cut_hz]",
        "filter <low_cut_hz> <high_cut_hz>",
        "tune-step <+/-hz|small|medium|large>",
        "step-pair <+/-n>",
        "volume <percent>",
        "volume-step <delta_percent>",
        "agc [on|off|hang on|off|threshold <value>|slope <value>|decay <ms>|gain <value>|set key=value ...]",
        "store <n>",
        "store all <n>",
        "recall <n>",
        "duration <seconds>",
        "frames <max_snd_frames>",
        "dashboard",
        "play-plan",
        "play --allow-live [--null-sink]",
        "play-bg --allow-live [--null-sink]",
        "stop",
        "wait [seconds]",
        "operation-status",
        "record-plan <output.wav>",
        "record <output.wav> --allow-live [--overwrite]",
        "record-bg <output.wav> --allow-live [--overwrite]",
        "capture-plan <output.jsonl>",
        "capture <output.jsonl> --allow-live [--overwrite]",
        "capture-bg <output.jsonl> --allow-live [--overwrite]",
        "help",
        "quit",
        "aliases: ?=status, re=receiver, ad=add-receiver, tu=tune, mo=mode, fi=filter, ag=agc, du=duration, fr=frames, pb=play-bg, rb=record-bg, cb=capture-bg, sp=stop, he=help, q/qu=quit",
    ]


def run_script(lines: Iterable[str], controller: ClientController | None = None) -> list[dict[str, Any]]:
    """Run command lines through a controller and collect responses."""
    controller = controller or ClientController()
    responses: list[dict[str, Any]] = []
    for line in lines:
        response = controller.execute(line)
        if response is not None:
            responses.append(response)
        if not controller.running:
            break
    return responses


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Basic KiwiSDR client control shell")
    parser.add_argument("--script", type=Path, help="read commands from a script file instead of stdin")
    parser.add_argument("--json", action="store_true", help="emit JSONL responses")
    parser.add_argument("--tui", action="store_true", help="run the curses TUI")
    return parser


def _print_response(response: dict[str, Any], *, as_json: bool) -> None:
    if as_json:
        print(json.dumps(response, sort_keys=True))
    else:
        print(response)


def main(argv: list[str] | None = None) -> int:
    parser = build_arg_parser()
    args = parser.parse_args(argv)
    controller = ClientController()
    try:
        if args.tui:
            from kiwi_client.tui import run_tui

            run_tui(controller)
            return 0
        if args.script:
            lines = args.script.read_text(encoding="utf-8").splitlines()
            for response in run_script(lines, controller):
                _print_response(response, as_json=args.json)
        else:
            while controller.running:
                try:
                    line = input("kiwi> ")
                except EOFError:
                    break
                try:
                    response = controller.execute(line)
                    if response is not None:
                        _print_response(response, as_json=args.json)
                except ClientCommandError as exc:
                    print(f"error: {exc}")
    except ClientCommandError as exc:
        parser.error(str(exc))
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
