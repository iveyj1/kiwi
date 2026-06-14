"""Basic scriptable KiwiSDR client control surface.

This is the first Milestone 6 client shell. It manages receiver/frequency/mode
state and can print guarded live-operation plans without opening network
connections. Actual play/record/capture operations remain in their dedicated
modules.
"""

from __future__ import annotations

import argparse
import json
import shlex
from dataclasses import asdict, dataclass, replace
from pathlib import Path
from typing import Any, Iterable

from kiwi_client.live_capture import LiveSndCaptureConfig
from kiwi_client.live_play import LiveSndPlaybackConfig
from kiwi_client.live_record import LiveSndWavRecordConfig


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


class ClientController:
    """Apply simple user commands to client state and produce plans."""

    def __init__(self, state: ClientState | None = None) -> None:
        self.state = state or ClientState()
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
        if command == "play-plan":
            self._require_arg_count(args, 0, "play-plan")
            return {"type": "play-plan", "plan": self._playback_config().dry_run_plan()}
        if command == "record-plan":
            self._require_arg_count(args, 1, "record-plan <output.wav>")
            return {"type": "record-plan", "plan": self._record_config(Path(args[0])).dry_run_plan()}
        if command == "capture-plan":
            self._require_arg_count(args, 1, "capture-plan <output.jsonl>")
            return {"type": "capture-plan", "plan": self._capture_config(Path(args[0])).dry_run_plan()}
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

    def _playback_config(self) -> LiveSndPlaybackConfig:
        return LiveSndPlaybackConfig(
            host=self.state.host,
            port=self.state.port,
            user=self.state.user,
            frequency_khz=self.state.frequency_khz,
            mode=self.state.mode,
            low_cut_hz=self.state.low_cut_hz,
            high_cut_hz=self.state.high_cut_hz,
        )

    def _record_config(self, output: Path) -> LiveSndWavRecordConfig:
        return LiveSndWavRecordConfig(
            host=self.state.host,
            port=self.state.port,
            output=output,
            user=self.state.user,
            frequency_khz=self.state.frequency_khz,
            mode=self.state.mode,
            low_cut_hz=self.state.low_cut_hz,
            high_cut_hz=self.state.high_cut_hz,
        )

    def _capture_config(self, output: Path) -> LiveSndCaptureConfig:
        return LiveSndCaptureConfig(
            host=self.state.host,
            port=self.state.port,
            output=output,
            user=self.state.user,
            frequency_khz=self.state.frequency_khz,
            mode=self.state.mode,
            low_cut_hz=self.state.low_cut_hz,
            high_cut_hz=self.state.high_cut_hz,
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
        "play-plan",
        "record-plan <output.wav>",
        "capture-plan <output.jsonl>",
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
