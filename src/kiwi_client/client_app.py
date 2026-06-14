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
import shlex
from dataclasses import asdict, dataclass, replace
from pathlib import Path
from threading import Event
from typing import Any, Iterable, Protocol

from kiwi_client.live_capture import LiveSndCaptureConfig, capture_live_snd
from kiwi_client.live_play import LiveSndPlaybackConfig, play_live_snd
from kiwi_client.live_record import LiveSndWavRecordConfig, record_live_snd_wav
from kiwi_client.live_worker import BackgroundOperation
from kiwi_client.playback import NullAudioSink, SoundDeviceSink


DEFAULT_LOW_CUT_HZ = -5000
DEFAULT_HIGH_CUT_HZ = 5000


@dataclass(frozen=True)
class ClientState:
    """Interactive client state independent of transport/UI."""

    host: str = "10.0.0.40"
    port: int = 8073
    frequency_khz: float = 5000.0
    mode: str = "am"
    low_cut_hz: int = DEFAULT_LOW_CUT_HZ
    high_cut_hz: int = DEFAULT_HIGH_CUT_HZ
    user: str = "kiwi-client"
    duration_seconds: float = 60.0
    max_frames: int = 1500
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

    def play(self, config: LiveSndPlaybackConfig, *, null_sink: bool, stop_event: Event | None = None) -> dict[str, Any]: ...

    def record(self, config: LiveSndWavRecordConfig) -> dict[str, Any]: ...

    def capture(self, config: LiveSndCaptureConfig) -> dict[str, Any]: ...


class LiveClientOperations:
    """Default operations that call guarded live play/record/capture modules."""

    def play(self, config: LiveSndPlaybackConfig, *, null_sink: bool, stop_event: Event | None = None) -> dict[str, Any]:
        sink = NullAudioSink() if null_sink else SoundDeviceSink()
        result = asyncio.run(play_live_snd(config, sink, allow_live=True, dry_run=null_sink, stop_event=stop_event))
        data = asdict(result)
        data["path"] = str(result.path)
        return data

    def record(self, config: LiveSndWavRecordConfig) -> dict[str, Any]:
        result = asyncio.run(record_live_snd_wav(config, allow_live=True))
        data = asdict(result)
        data["path"] = str(result.path)
        return data

    def capture(self, config: LiveSndCaptureConfig) -> dict[str, Any]:
        path = asyncio.run(capture_live_snd(config, allow_live=True))
        return {"path": str(path)}


class ClientController:
    """Apply simple user commands to client state and produce plans."""

    def __init__(
        self,
        state: ClientState | None = None,
        operations: ClientOperations | None = None,
        background: BackgroundOperation | None = None,
    ) -> None:
        self.state = state or ClientState()
        self.operations = operations or LiveClientOperations()
        self.background = background or BackgroundOperation()
        self.running = True

    def execute(self, line: str) -> dict[str, Any] | None:
        """Execute one shell command and return a JSON-serializable response."""
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            return None
        parts = shlex.split(stripped)
        command = parts[0].lower()
        args = parts[1:]

        if command in {"quit", "exit"}:
            self.running = False
            return {"type": "quit"}
        if command == "help":
            return {"type": "help", "commands": available_commands()}
        if command == "status":
            return {"type": "status", "state": self.state.as_dict()}
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
            return {"type": "state", "state": self.state.as_dict()}
        if command == "mode":
            if len(args) not in {1, 3}:
                raise ClientCommandError("usage: mode <mode> [low_cut_hz high_cut_hz]")
            mode = args[0].lower()
            if len(args) == 3:
                self.state = replace(self.state, mode=mode, low_cut_hz=int(args[1]), high_cut_hz=int(args[2]))
            else:
                self.state = replace(self.state, mode=mode)
            return {"type": "state", "state": self.state.as_dict()}
        if command == "filter":
            self._require_arg_count(args, 2, "filter <low_cut_hz> <high_cut_hz>")
            self.state = replace(self.state, low_cut_hz=int(args[0]), high_cut_hz=int(args[1]))
            return {"type": "state", "state": self.state.as_dict()}
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
                lambda stop_event: self.operations.play(config, null_sink=null_sink, stop_event=stop_event),
            )
            return {"type": "operation-status", "operation": status.as_dict()}
        if command == "stop":
            return {"type": "operation-status", "operation": self.background.stop().as_dict()}
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
        if command == "capture":
            positional, flags = self._parse_flags(args, {"--allow-live", "--overwrite"})
            self._require_arg_count(positional, 1, "capture <output.jsonl> --allow-live [--overwrite]")
            self._require_allow_live(flags, "capture-plan <output.jsonl>")
            return {
                "type": "capture",
                "result": self.operations.capture(self._capture_config(Path(positional[0]), overwrite="--overwrite" in flags)),
            }
        raise ClientCommandError(f"unknown command: {command}")

    def _with_receiver(self, value: str) -> ClientState:
        if ":" in value:
            host, port = value.rsplit(":", 1)
            return replace(self.state, host=host, port=int(port))
        return replace(self.state, host=value)

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

    @staticmethod
    def _require_allow_live(flags: set[str], plan_command: str) -> None:
        if "--allow-live" not in flags:
            raise ClientCommandError(f"refusing live operation without --allow-live; use `{plan_command}` first")

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
        )


def available_commands() -> list[str]:
    return [
        "status",
        "connect",
        "disconnect",
        "receiver <host>[:port]",
        "tune <frequency_khz>",
        "mode <mode> [low_cut_hz high_cut_hz]",
        "filter <low_cut_hz> <high_cut_hz>",
        "duration <seconds>",
        "frames <max_snd_frames>",
        "dashboard",
        "play-plan",
        "play --allow-live [--null-sink]",
        "play-bg --allow-live [--null-sink]",
        "stop",
        "operation-status",
        "record-plan <output.wav>",
        "record <output.wav> --allow-live [--overwrite]",
        "capture-plan <output.jsonl>",
        "capture <output.jsonl> --allow-live [--overwrite]",
        "help",
        "quit",
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
