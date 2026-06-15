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
from dataclasses import asdict, dataclass, replace
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


DEFAULT_LOW_CUT_HZ = -5000
DEFAULT_HIGH_CUT_HZ = 5000


@dataclass(frozen=True)
class ClientState:
    """Interactive client state independent of transport/UI."""

    host: str = "10.0.0.41"
    port: int = 8073
    frequency_khz: float = 5000.0
    mode: str = "am"
    low_cut_hz: int = DEFAULT_LOW_CUT_HZ
    high_cut_hz: int = DEFAULT_HIGH_CUT_HZ
    user: str = "kiwi-client"
    duration_seconds: float = 60.0
    max_frames: int = 1500
    volume_percent: int = 100
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

    def as_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["receiver"] = self.receiver
        return data


class ClientCommandError(ValueError):
    """Raised for invalid client shell commands."""


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
    ) -> None:
        self.state = state or ClientState()
        self.operations = operations or LiveClientOperations()
        self.background = background or BackgroundOperation()
        self.allow_live_default = allow_live_default
        self.volume_control = volume_control or SystemVolumeControl()
        self.presets: dict[int, dict[str, Any]] = dict(presets or {})
        self.running = True

    def execute(self, line: str) -> dict[str, Any] | None:
        """Execute one shell command and return a JSON-serializable response."""
        stripped = line.strip()
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
            return {"type": "status", "state": self._state_dict_with_connection()}
        if command == "connect":
            self.state = replace(self.state, connected=True)
            return {"type": "state", "state": self.state.as_dict()}
        if command == "disconnect":
            self.state = replace(self.state, connected=False)
            return {"type": "state", "state": self.state.as_dict()}
        if command == "receiver":
            self._require_arg_count(args, 1, "receiver <host>[:port]")
            self.state = self._with_receiver(args[0])
            return {"type": "state", "state": self.state.as_dict()}
        if command == "tune":
            self._require_arg_count(args, 1, "tune <frequency_khz>")
            self.state = replace(self.state, frequency_khz=float(args[0]))
            return self._state_response()
        if command == "mode":
            if len(args) not in {1, 3}:
                raise ClientCommandError("usage: mode <mode> [low_cut_hz high_cut_hz]")
            mode = args[0].lower()
            if len(args) == 3:
                self.state = replace(self.state, mode=mode, low_cut_hz=int(args[1]), high_cut_hz=int(args[2]))
            else:
                self.state = replace(self.state, mode=mode)
            return self._state_response()
        if command == "filter":
            self._require_arg_count(args, 2, "filter <low_cut_hz> <high_cut_hz>")
            self.state = replace(self.state, low_cut_hz=int(args[0]), high_cut_hz=int(args[1]))
            return self._state_response()
        if command == "tune-step":
            self._require_arg_count(args, 1, "tune-step <+/-hz|small|medium|large>")
            delta_hz = self._parse_tune_step_hz(args[0])
            self.state = replace(self.state, frequency_khz=self.state.frequency_khz + delta_hz / 1000.0)
            return self._state_response()
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
            return self._recall_preset(int(args[0]))
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
            config = self._playback_config()
            null_sink = "--null-sink" in flags
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
            return {"type": "operation-status", "operation": status.as_dict()}
        if command == "stop":
            return {"type": "operation-status", "operation": self.background.stop().as_dict()}
        if command == "wait":
            if len(args) > 1:
                raise ClientCommandError("usage: wait [seconds]")
            timeout = float(args[0]) if args else None
            return {"type": "operation-status", "operation": self.background.join(timeout=timeout).as_dict()}
        if command == "operation-status":
            return {"type": "operation-status", "operation": self.background.status().as_dict()}
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

    def _with_receiver(self, value: str) -> ClientState:
        if ":" in value:
            host, port = value.rsplit(":", 1)
            return replace(self.state, host=host, port=int(port))
        return replace(self.state, host=value)

    def _state_response(self) -> dict[str, Any]:
        command = encode_modulation(
            self.state.mode,
            self.state.low_cut_hz,
            self.state.high_cut_hz,
            self.state.frequency_khz,
        )
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

    def _handle_store(self, args: list[str]) -> dict[str, Any]:
        if len(args) == 1:
            preset_id = int(args[0])
            self.presets[preset_id] = minimal_preset(self.state)
            return {"type": "preset", "preset": preset_id, "scope": "minimal", "state": self.state.as_dict()}
        if len(args) == 2 and args[0].lower() == "all":
            preset_id = int(args[1])
            self.presets[preset_id] = full_preset(self.state)
            return {"type": "preset", "preset": preset_id, "scope": "all", "state": self.state.as_dict()}
        raise ClientCommandError("usage: store <n> | store all <n>")

    def _recall_preset(self, preset_id: int) -> dict[str, Any]:
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
    def _parse_tune_step_hz(value: str) -> int:
        sign = 1
        token = value.strip().lower()
        if token.startswith("+"):
            token = token[1:]
        elif token.startswith("-"):
            token = token[1:]
            sign = -1
        named = {"small": 100, "medium": 1000, "large": 5000}
        hz = named[token] if token in named else int(token)
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
            mode=self.state.mode,
            low_cut_hz=self.state.low_cut_hz,
            high_cut_hz=self.state.high_cut_hz,
            duration_seconds=self.state.duration_seconds,
            max_frames=self.state.max_frames,
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
            mode=self.state.mode,
            low_cut_hz=self.state.low_cut_hz,
            high_cut_hz=self.state.high_cut_hz,
            duration_seconds=self.state.duration_seconds,
            max_frames=self.state.max_frames,
            overwrite=overwrite,
            receivers_restricted=self.state.receivers_restricted,
            allowed_receivers=self.state.allowed_receivers,
        )


def command_aliases() -> dict[str, str]:
    """Return short command aliases for interactive use."""
    return {
        "?": "status",
        "re": "receiver",
        "tu": "tune",
        "mo": "mode",
        "fi": "filter",
        "ag": "agc",
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
        "tune <frequency_khz>",
        "mode <mode> [low_cut_hz high_cut_hz]",
        "filter <low_cut_hz> <high_cut_hz>",
        "tune-step <+/-hz|small|medium|large>",
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
        "aliases: ?=status, re=receiver, tu=tune, mo=mode, fi=filter, ag=agc, du=duration, fr=frames, pb=play-bg, rb=record-bg, cb=capture-bg, sp=stop, he=help, q/qu=quit",
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
