"""Guarded direct SND-to-WAV recording.

The core session logic is testable with ReplayTransport. Live network use is
still gated by local receiver allowlist and explicit --allow-live.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from threading import Event
from typing import Any, Callable

from kiwi_client.commands import encode_ar_ok, encode_auth, encode_basic_snd_setup
from kiwi_client.live_capture import (
    LOCAL_RECEIVERS,
    MAX_DURATION_SECONDS,
    MAX_FRAMES,
    WEBSOCKET_CLOSE_TIMEOUT_SECONDS,
    LiveCaptureError,
    sorted_receiver_names,
)
from kiwi_client.recorder import SndWavRecorder, WavRecordingResult
from kiwi_client.transport import ReplayTransport


@dataclass(frozen=True)
class LiveSndWavRecordConfig:
    """Configuration for one short direct SND-to-WAV recording."""

    host: str
    port: int
    output: Path
    user: str = "kiwi-client"
    frequency_khz: float = 4625.0
    mode: str = "am"
    low_cut_hz: int = -4900
    high_cut_hz: int = 4900
    duration_seconds: float = 3.0
    max_frames: int = 20
    compression: bool = False
    timestamp: int | None = None
    overwrite: bool = False

    @property
    def receiver(self) -> str:
        return f"{self.host}:{self.port}"

    def validate(self) -> None:
        if (self.host, self.port) not in LOCAL_RECEIVERS:
            raise LiveCaptureError(f"receiver must be one of the local receivers: {sorted_receiver_names()}")
        if not (0 < self.duration_seconds <= MAX_DURATION_SECONDS):
            raise LiveCaptureError(f"duration must be > 0 and <= {MAX_DURATION_SECONDS} seconds")
        if not (1 <= self.max_frames <= MAX_FRAMES):
            raise LiveCaptureError(f"max_frames must be between 1 and {MAX_FRAMES}")
        if self.compression:
            raise LiveCaptureError("first direct WAV recording path must use compression=0")
        if self.output.exists() and not self.overwrite:
            raise LiveCaptureError(f"output already exists; use --overwrite to replace: {self.output}")

    def websocket_uri(self) -> str:
        timestamp = self.timestamp if self.timestamp is not None else int(time.time())
        return f"ws://{self.host}:{self.port}/{timestamp}/SND"

    def setup_commands(self) -> list[str]:
        return encode_basic_snd_setup(
            user=self.user,
            frequency_khz=self.frequency_khz,
            modulation=self.mode,
            low_cut=self.low_cut_hz,
            high_cut=self.high_cut_hz,
            compression=self.compression,
        )

    def dry_run_plan(self) -> dict[str, Any]:
        return {
            "receiver": self.receiver,
            "websocket_uri": self.websocket_uri(),
            "output": str(self.output),
            "frequency_khz": self.frequency_khz,
            "mode": self.mode,
            "low_cut_hz": self.low_cut_hz,
            "high_cut_hz": self.high_cut_hz,
            "duration_seconds": self.duration_seconds,
            "max_frames": self.max_frames,
            "compression": self.compression,
            "initial_commands": [encode_auth()],
            "dynamic_commands": ["SET AR OK in=<audio_rate> out=44100", *self.setup_commands()],
        }


def _session_command_state(recorder: SndWavRecorder, sent_ar_ok: bool, sent_setup: bool) -> tuple[list[str], bool, bool]:
    commands: list[str] = []
    if recorder.state.audio_rate is not None and not sent_ar_ok:
        commands.append(encode_ar_ok(recorder.state.audio_rate))
        sent_ar_ok = True
    if recorder.state.sample_rate is not None and sent_ar_ok and not sent_setup:
        sent_setup = True
    return commands, sent_ar_ok, sent_setup


def record_replay_snd_wav(transport: ReplayTransport, output: str | Path, *, config: LiveSndWavRecordConfig) -> WavRecordingResult:
    """Record a strict replayed SND session directly to WAV."""
    recorder = SndWavRecorder()
    sent_ar_ok = False
    sent_setup = False

    transport.send(encode_auth())
    while not transport.done:
        event = transport.receive()
        if event.type == "msg" and event.text is not None:
            recorder.add_msg(event.text)
            commands, sent_ar_ok, should_send_setup = _session_command_state(recorder, sent_ar_ok, sent_setup)
            for command in commands:
                transport.send(command)
            if should_send_setup and not sent_setup:
                for command in config.setup_commands():
                    transport.send(command)
                sent_setup = True
        elif event.type == "binary" and event.payload is not None:
            recorder.add_snd_payload(event.payload)
    return recorder.write_wav(output)


async def record_live_snd_wav(
    config: LiveSndWavRecordConfig,
    *,
    allow_live: bool = False,
    stop_event: Event | None = None,
    status_callback: Callable[[dict], None] | None = None,
) -> WavRecordingResult:
    """Run one guarded live SND-to-WAV recording."""
    config.validate()
    if not allow_live:
        raise LiveCaptureError("live recording requires allow_live=True")
    try:
        import websockets
    except ImportError as exc:
        raise LiveCaptureError("live recording requires optional dependency: pip install '.[live]'") from exc

    recorder = SndWavRecorder()
    start = time.monotonic()
    snd_frames = 0
    sent_ar_ok = False
    sent_setup = False

    async with websockets.connect(
        config.websocket_uri(),
        max_queue=0,
        close_timeout=WEBSOCKET_CLOSE_TIMEOUT_SECONDS,
    ) as websocket:
        await websocket.send(encode_auth())
        while snd_frames < config.max_frames and (time.monotonic() - start) < config.duration_seconds:
            if stop_event is not None and stop_event.is_set():
                break
            remaining = config.duration_seconds - (time.monotonic() - start)
            if remaining <= 0:
                break
            try:
                message = await asyncio.wait_for(websocket.recv(), timeout=remaining)
            except asyncio.TimeoutError:
                break

            if isinstance(message, str):
                text = message
                recorder.add_msg(text)
            else:
                payload = bytes(message)
                if payload.startswith(b"MSG"):
                    recorder.add_msg(payload.decode("utf-8", errors="replace"))
                else:
                    recorder.add_snd_payload(payload)
                    if payload.startswith(b"SND"):
                        snd_frames += 1
                        if status_callback is not None:
                            status_callback(recorder.status_metrics())
                    continue

            commands, sent_ar_ok, should_send_setup = _session_command_state(recorder, sent_ar_ok, sent_setup)
            for command in commands:
                await websocket.send(command)
            if should_send_setup and not sent_setup:
                for command in config.setup_commands():
                    await websocket.send(command)
                sent_setup = True

    return recorder.write_wav(config.output)


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Guarded short local KiwiSDR SND-to-WAV recording")
    parser.add_argument("--host", default="10.0.0.40", choices=[host for host, _ in sorted(LOCAL_RECEIVERS)])
    parser.add_argument("--port", type=int, default=8073)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--user", default="kiwi-client")
    parser.add_argument("--frequency-khz", type=float, default=4625.0)
    parser.add_argument("--mode", default="am")
    parser.add_argument("--low-cut-hz", type=int, default=-4900)
    parser.add_argument("--high-cut-hz", type=int, default=4900)
    parser.add_argument("--duration-seconds", type=float, default=3.0)
    parser.add_argument("--max-frames", type=int, default=20)
    parser.add_argument("--timestamp", type=int)
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument("--dry-run", action="store_true", help="print recording plan and do not connect")
    parser.add_argument("--allow-live", action="store_true", help="required to make a live receiver connection")
    parser.add_argument("--json", action="store_true", help="print recording summary as JSON")
    return parser


def config_from_args(args: argparse.Namespace) -> LiveSndWavRecordConfig:
    return LiveSndWavRecordConfig(
        host=args.host,
        port=args.port,
        output=args.output,
        user=args.user,
        frequency_khz=args.frequency_khz,
        mode=args.mode,
        low_cut_hz=args.low_cut_hz,
        high_cut_hz=args.high_cut_hz,
        duration_seconds=args.duration_seconds,
        max_frames=args.max_frames,
        timestamp=args.timestamp,
        overwrite=args.overwrite,
    )


def main(argv: list[str] | None = None) -> int:
    parser = build_arg_parser()
    args = parser.parse_args(argv)
    config = config_from_args(args)
    try:
        config.validate()
        if args.dry_run:
            print(json.dumps(config.dry_run_plan(), indent=2, sort_keys=True))
            return 0
        if not args.allow_live:
            raise LiveCaptureError("refusing to connect without --allow-live; use --dry-run to inspect the plan")
        result = asyncio.run(record_live_snd_wav(config, allow_live=True))
        if args.json:
            data = asdict(result)
            data["path"] = str(result.path)
            print(json.dumps(data, indent=2, sort_keys=True))
        else:
            print(result)
        return 0
    except LiveCaptureError as exc:
        parser.error(str(exc))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
