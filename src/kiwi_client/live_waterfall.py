"""Guarded live KiwiSDR W/F capture and ASCII preview."""

from __future__ import annotations

import argparse
import asyncio
import json
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from threading import Event
from typing import Any, Callable
from zoneinfo import ZoneInfo

from kiwi_client.capture import JsonlCaptureWriter, WaterfallCaptureMetadata
from kiwi_client.commands import encode_auth, encode_keepalive
from kiwi_client.live_capture import (
    LiveCaptureError,
    allowed_receiver_names,
    keepalive_due,
    raise_for_kiwi_error,
    receive_poll_timeout,
    snd_loop_allowed,
)
from kiwi_client.protocol import parse_msg
from kiwi_client.waterfall import WaterfallSequenceTracker, parse_waterfall_uncompressed
from kiwi_client.waterfall_render import DEFAULT_ASCII_RAMP, render_ascii_waterfall_row

WEBSOCKET_CLOSE_TIMEOUT_SECONDS = 0.25


@dataclass(frozen=True)
class LiveWaterfallCaptureConfig:
    """Configuration for one short, attended W/F capture."""

    host: str
    port: int
    output: Path
    center_khz: float = 5000.0
    zoom: int = 0
    maxdb: int = 0
    mindb: int = -110
    speed: int = 1
    interp: int = 13
    duration_seconds: float = 3.0
    max_frames: int = 5
    compression: bool = False
    timestamp: int | None = None
    overwrite: bool = False
    receivers_restricted: bool = True
    allowed_receivers: tuple[str, ...] | None = None

    @property
    def receiver(self) -> str:
        return f"{self.host}:{self.port}"

    def validate(self) -> None:
        """Validate guardrails before any live network operation."""
        if self.receivers_restricted and self.receiver not in allowed_receiver_names(self.allowed_receivers):
            raise LiveCaptureError(f"receiver must be one of the allowed receivers: {allowed_receiver_names(self.allowed_receivers)}")
        if self.duration_seconds < 0:
            raise LiveCaptureError("duration must be >= 0 seconds; 0 means unlimited")
        if self.max_frames < 0:
            raise LiveCaptureError("max_frames must be >= 0; 0 means unlimited")
        if self.zoom < 0:
            raise LiveCaptureError("zoom must be >= 0")
        if self.speed < 1 or self.speed > 4:
            raise LiveCaptureError("waterfall speed must be in range 1..4")
        if self.maxdb <= self.mindb:
            raise LiveCaptureError("maxdb must be greater than mindb")
        if self.compression:
            raise LiveCaptureError("first live W/F capture must use wf_comp=0 for existing parser coverage")
        if self.output.exists() and not self.overwrite:
            raise LiveCaptureError(f"output already exists; use --overwrite to replace: {self.output}")

    def websocket_uri(self) -> str:
        """Return the KiwiSDR W/F WebSocket URI for this capture."""
        timestamp = self.timestamp if self.timestamp is not None else int(time.time())
        return f"ws://{self.host}:{self.port}/{timestamp}/W/F"

    def setup_commands(self) -> list[str]:
        """Return setup commands sent after auth."""
        return [
            f"SET zoom={self.zoom} cf={self.center_khz:.3f}",
            f"SET maxdb={self.maxdb} mindb={self.mindb}",
            f"SET wf_speed={self.speed}",
            "SET wf_comp=0",
            f"SET interp={self.interp}",
            encode_keepalive(),
        ]

    def dry_run_plan(self) -> dict[str, Any]:
        """Return a JSON-serializable plan without connecting."""
        return {
            "receiver": self.receiver,
            "websocket_uri": self.websocket_uri(),
            "output": str(self.output),
            "center_khz": self.center_khz,
            "zoom": self.zoom,
            "maxdb": self.maxdb,
            "mindb": self.mindb,
            "speed": self.speed,
            "interp": self.interp,
            "duration_seconds": self.duration_seconds,
            "max_frames": self.max_frames,
            "compression": self.compression,
            "commands": [encode_auth(), *self.setup_commands()],
        }


def _capture_metadata(config: LiveWaterfallCaptureConfig) -> WaterfallCaptureMetadata:
    now_utc = datetime.now(tz=ZoneInfo("UTC"))
    now_local = datetime.now().astimezone()
    return WaterfallCaptureMetadata(
        receiver=config.receiver,
        utc_time=now_utc.isoformat(),
        local_time=now_local.isoformat(),
        center_khz=config.center_khz,
        zoom=config.zoom,
        maxdb=config.maxdb,
        mindb=config.mindb,
        speed=config.speed,
        compression=config.compression,
        notes="short guarded local W/F capture",
    )


async def capture_live_waterfall(
    config: LiveWaterfallCaptureConfig,
    *,
    allow_live: bool = False,
    stop_event: Event | None = None,
    status_callback: Callable[[dict], None] | None = None,
    websocket_connect: Callable[..., Any] | None = None,
) -> Path:
    """Run one guarded live W/F capture and write a JSONL fixture."""
    config.validate()
    if not allow_live:
        raise LiveCaptureError("live waterfall capture requires allow_live=True")

    if websocket_connect is None:
        try:
            import websockets
        except ImportError as exc:
            raise LiveCaptureError("live waterfall capture requires optional dependency: pip install '.[live]'") from exc
        websocket_connect = websockets.connect

    writer = JsonlCaptureWriter(_capture_metadata(config))
    start = time.monotonic()
    frames = 0
    last_keepalive = start
    sequence = WaterfallSequenceTracker()

    async with websocket_connect(
        config.websocket_uri(),
        max_queue=0,
        close_timeout=WEBSOCKET_CLOSE_TIMEOUT_SECONDS,
    ) as websocket:
        for command in [encode_auth(), *config.setup_commands()]:
            writer.add_tx_cmd(time.monotonic() - start, command, stream="wf")
            await websocket.send(command)

        while snd_loop_allowed(start, frames, duration_seconds=config.duration_seconds, max_frames=config.max_frames):
            if stop_event is not None and stop_event.is_set():
                break
            now = time.monotonic()
            if keepalive_due(now, last_keepalive, sent_setup=True):
                command = encode_keepalive()
                writer.add_tx_cmd(now - start, command, stream="wf")
                await websocket.send(command)
                last_keepalive = now
            remaining = receive_poll_timeout(start, duration_seconds=config.duration_seconds)
            if remaining == 0:
                break
            try:
                message = await asyncio.wait_for(websocket.recv(), timeout=remaining)
            except asyncio.TimeoutError:
                continue
            t = time.monotonic() - start
            if isinstance(message, str):
                text = message
                writer.add_rx_msg(t, text, stream="wf")
                params = parse_msg(text).params
                raise_for_kiwi_error(params, receiver=config.receiver)
                continue

            payload = bytes(message)
            if payload.startswith(b"MSG"):
                text = payload.decode("utf-8", errors="replace")
                writer.add_rx_msg(t, text, stream="wf")
                params = parse_msg(text).params
                raise_for_kiwi_error(params, receiver=config.receiver)
                continue

            writer.add_rx_binary(t, payload, stream="wf")
            if payload.startswith(b"W/F"):
                frame = parse_waterfall_uncompressed(payload)
                status = sequence.observe(frame)
                frames += 1
                if status_callback is not None:
                    metrics = {
                        "wf_seq": frame.sequence,
                        "wf_frames": frames,
                        "sequence_gaps": status.missing_count,
                        "out_of_order": status.out_of_order,
                        "ascii_row": render_ascii_waterfall_row(frame, min_dbm=config.mindb, max_dbm=config.maxdb),
                    }
                    status_callback(metrics)

    writer.write(config.output)
    return config.output


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Guarded short local KiwiSDR W/F capture")
    parser.add_argument("--host", default="10.0.0.40")
    parser.add_argument("--port", type=int, default=8073)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--center-khz", type=float, default=5000.0)
    parser.add_argument("--zoom", type=int, default=0)
    parser.add_argument("--max-db", type=int, default=0)
    parser.add_argument("--min-db", type=int, default=-110)
    parser.add_argument("--speed", type=int, default=1)
    parser.add_argument("--interp", type=int, default=13)
    parser.add_argument("--duration-seconds", type=float, default=3.0)
    parser.add_argument("--max-frames", type=int, default=5)
    parser.add_argument("--timestamp", type=int)
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--allow-live", action="store_true")
    parser.add_argument("--json", action="store_true")
    return parser


def config_from_args(args: argparse.Namespace) -> LiveWaterfallCaptureConfig:
    return LiveWaterfallCaptureConfig(
        host=args.host,
        port=args.port,
        output=args.output,
        center_khz=args.center_khz,
        zoom=args.zoom,
        maxdb=args.max_db,
        mindb=args.min_db,
        speed=args.speed,
        interp=args.interp,
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
            parser.error("live waterfall capture requires --allow-live; use --dry-run for a plan")
        path = asyncio.run(capture_live_waterfall(config, allow_live=True))
        if args.json:
            print(json.dumps({"path": str(path)}, sort_keys=True))
        else:
            print(path)
        return 0
    except LiveCaptureError as exc:
        parser.error(str(exc))
    return 2


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
