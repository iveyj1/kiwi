"""Guarded live SND capture tool.

This module is intentionally conservative. Importing it or running tests never
connects to a receiver. A live connection requires the explicit `--allow-live`
CLI flag and a local receiver address.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from kiwi_client.capture import JsonlCaptureWriter, SndCaptureMetadata
from kiwi_client.commands import encode_ar_ok, encode_auth, encode_basic_snd_setup
from kiwi_client.protocol import parse_msg
from kiwi_client.receiver_model import ReceiverState

LOCAL_RECEIVERS = {("10.0.0.40", 8073), ("10.0.0.41", 8073)}
MAX_DURATION_SECONDS = 5.0
MAX_FRAMES = 100


class LiveCaptureError(RuntimeError):
    """Raised when live capture is not allowed or cannot proceed."""


@dataclass(frozen=True)
class LiveSndCaptureConfig:
    """Configuration for one short, attended SND capture."""

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
        """Validate guardrails before any live network operation."""
        if (self.host, self.port) not in LOCAL_RECEIVERS:
            raise LiveCaptureError(f"receiver must be one of the local receivers: {sorted_receiver_names()}")
        if not (0 < self.duration_seconds <= MAX_DURATION_SECONDS):
            raise LiveCaptureError(f"duration must be > 0 and <= {MAX_DURATION_SECONDS} seconds")
        if not (1 <= self.max_frames <= MAX_FRAMES):
            raise LiveCaptureError(f"max_frames must be between 1 and {MAX_FRAMES}")
        if self.compression:
            raise LiveCaptureError("first live SND capture must use compression=0 for existing PCM parser coverage")
        if self.output.exists() and not self.overwrite:
            raise LiveCaptureError(f"output already exists; use --overwrite to replace: {self.output}")

    def websocket_uri(self) -> str:
        """Return the KiwiSDR SND WebSocket URI for this capture."""
        timestamp = self.timestamp if self.timestamp is not None else int(time.time())
        return f"ws://{self.host}:{self.port}/{timestamp}/SND"

    def setup_commands(self) -> list[str]:
        """Return setup commands after audio-rate acknowledgement."""
        return encode_basic_snd_setup(
            user=self.user,
            frequency_khz=self.frequency_khz,
            modulation=self.mode,
            low_cut=self.low_cut_hz,
            high_cut=self.high_cut_hz,
            compression=self.compression,
        )

    def dry_run_plan(self) -> dict[str, Any]:
        """Return a JSON-serializable plan without connecting."""
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


def sorted_receiver_names() -> list[str]:
    """Return local receiver names for user-facing messages."""
    return [f"{host}:{port}" for host, port in sorted(LOCAL_RECEIVERS)]


def _capture_metadata(config: LiveSndCaptureConfig) -> SndCaptureMetadata:
    now_utc = datetime.now(tz=ZoneInfo("UTC"))
    now_local = datetime.now().astimezone()
    return SndCaptureMetadata(
        receiver=config.receiver,
        utc_time=now_utc.isoformat(),
        local_time=now_local.isoformat(),
        frequency_khz=config.frequency_khz,
        mode=config.mode,
        low_cut_hz=config.low_cut_hz,
        high_cut_hz=config.high_cut_hz,
        compression=config.compression,
        notes="short guarded local SND capture",
    )


async def capture_live_snd(config: LiveSndCaptureConfig, *, allow_live: bool = False) -> Path:
    """Run one guarded live SND capture and write a JSONL fixture.

    This function performs network I/O only when `allow_live=True` and all
    guardrails pass.
    """
    config.validate()
    if not allow_live:
        raise LiveCaptureError("live capture requires allow_live=True")

    try:
        import websockets
    except ImportError as exc:
        raise LiveCaptureError("live capture requires optional dependency: pip install '.[live]'") from exc

    writer = JsonlCaptureWriter(_capture_metadata(config))
    start = time.monotonic()
    frames = 0

    async with websockets.connect(config.websocket_uri(), max_queue=0) as websocket:
        auth_command = encode_auth()
        writer.add_tx_cmd(time.monotonic() - start, auth_command)
        await websocket.send(auth_command)

        state = ReceiverState()
        sent_ar_ok = False
        sent_setup = False

        while frames < config.max_frames and (time.monotonic() - start) < config.duration_seconds:
            remaining = config.duration_seconds - (time.monotonic() - start)
            if remaining <= 0:
                break
            try:
                message = await asyncio.wait_for(websocket.recv(), timeout=remaining)
            except asyncio.TimeoutError:
                break
            t = time.monotonic() - start

            if isinstance(message, str):
                text = message
                writer.add_rx_msg(t, text)
            else:
                payload = bytes(message)
                if payload.startswith(b"MSG"):
                    text = payload.decode("utf-8", errors="replace")
                    writer.add_rx_msg(t, text)
                else:
                    writer.add_rx_binary(t, payload)
                    if payload.startswith(b"SND"):
                        frames += 1
                    continue

            params = parse_msg(text).params
            state = state.apply_msg_params(params)
            if state.audio_rate is not None and not sent_ar_ok:
                command = encode_ar_ok(state.audio_rate)
                writer.add_tx_cmd(time.monotonic() - start, command)
                await websocket.send(command)
                sent_ar_ok = True
            if state.sample_rate is not None and sent_ar_ok and not sent_setup:
                for command in config.setup_commands():
                    writer.add_tx_cmd(time.monotonic() - start, command)
                    await websocket.send(command)
                sent_setup = True

    writer.write(config.output)
    return config.output


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Guarded short local KiwiSDR SND capture")
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
    parser.add_argument("--dry-run", action="store_true", help="print capture plan and do not connect")
    parser.add_argument("--allow-live", action="store_true", help="required to make a live receiver connection")
    return parser


def config_from_args(args: argparse.Namespace) -> LiveSndCaptureConfig:
    return LiveSndCaptureConfig(
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
        path = asyncio.run(capture_live_snd(config, allow_live=True))
        print(path)
        return 0
    except LiveCaptureError as exc:
        parser.error(str(exc))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
