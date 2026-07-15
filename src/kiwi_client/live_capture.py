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
from threading import Event
from typing import Any, Callable
from zoneinfo import ZoneInfo

from kiwi_client.audio import SndMetricsTracker
from kiwi_client.capture import JsonlCaptureWriter, SndCaptureMetadata
from kiwi_client.commands import encode_ar_ok, encode_auth, encode_basic_snd_setup, encode_keepalive
from kiwi_client.protocol import parse_msg, parse_snd_uncompressed_mono
from kiwi_client.receiver_model import ReceiverState

LOCAL_RECEIVERS = {("10.0.0.40", 8073), ("10.0.0.41", 8073)}
MAX_DURATION_SECONDS = 60.0
MAX_FRAMES = 1500
WEBSOCKET_CLOSE_TIMEOUT_SECONDS = 0.25
KEEPALIVE_INTERVAL_SECONDS = 30.0
RECEIVE_POLL_TIMEOUT_SECONDS = 0.5


class LiveCaptureError(RuntimeError):
    """Raised when live capture is not allowed or cannot proceed."""


def kiwi_error_from_msg_params(params: dict[str, str | None], *, receiver: str) -> str | None:
    """Return a user-facing Kiwi server error from MSG params, if present."""
    if "too_busy" in params:
        slots = params.get("too_busy") or "all"
        return f"server busy: all {slots} client slots are taken on {receiver}"
    if params.get("badp") == "1":
        return f"server busy or bad password: all no-password channels may be busy on {receiver}"
    if "down" in params:
        return f"server down: {receiver}"
    if "redirect" in params:
        return f"server redirected {receiver} to {params.get('redirect')}"
    return None


def raise_for_kiwi_error(params: dict[str, str | None], *, receiver: str) -> None:
    """Raise LiveCaptureError for known Kiwi server error MSG params."""
    error = kiwi_error_from_msg_params(params, receiver=receiver)
    if error is not None:
        raise LiveCaptureError(error)


@dataclass(frozen=True)
class LiveSndCaptureConfig:
    """Configuration for one short, attended SND capture."""

    host: str
    port: int
    output: Path
    user: str = "kiwi-client"
    frequency_khz: float = 4625.0
    radio_frequency_khz: float | None = None
    frequency_decimals: int = 3
    mode: str = "am"
    low_cut_hz: int = -4900
    high_cut_hz: int = 4900
    duration_seconds: float = 3.0
    max_frames: int = 20
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
        if self.compression:
            raise LiveCaptureError("first live SND capture must use compression=0 for existing PCM parser coverage")
        if self.output.exists() and not self.overwrite:
            raise LiveCaptureError(f"output already exists; use --overwrite to replace: {self.output}")

    def websocket_uri(self) -> str:
        """Return the KiwiSDR SND WebSocket URI for this capture."""
        timestamp = self.timestamp if self.timestamp is not None else int(time.time())
        return f"ws://{self.host}:{self.port}/{timestamp}/SND"

    @property
    def effective_radio_frequency_khz(self) -> float:
        return self.frequency_khz if self.radio_frequency_khz is None else self.radio_frequency_khz

    def setup_commands(self) -> list[str]:
        """Return setup commands after audio-rate acknowledgement."""
        return encode_basic_snd_setup(
            user=self.user,
            frequency_khz=self.effective_radio_frequency_khz,
            modulation=self.mode,
            frequency_decimals=self.frequency_decimals,
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
            "radio_frequency_khz": self.effective_radio_frequency_khz,
            "frequency_decimals": self.frequency_decimals,
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


def allowed_receiver_names(configured: tuple[str, ...] | None = None) -> tuple[str, ...]:
    """Return configured receiver allowlist names, defaulting to local receivers."""
    return tuple(configured or sorted_receiver_names())


def snd_loop_allowed(start: float, frames: int, *, duration_seconds: float, max_frames: int) -> bool:
    """Return true while a guarded SND loop should continue.

    A value of 0 for duration or max_frames means that limit is disabled.
    """
    within_frame_limit = max_frames == 0 or frames < max_frames
    within_time_limit = duration_seconds == 0 or (time.monotonic() - start) < duration_seconds
    return within_frame_limit and within_time_limit


def snd_loop_timeout(start: float, *, duration_seconds: float) -> float | None:
    """Return remaining timeout for one receive, or None when duration is unlimited."""
    if duration_seconds == 0:
        return None
    return max(0.0, duration_seconds - (time.monotonic() - start))


def receive_poll_timeout(start: float, *, duration_seconds: float, poll_seconds: float = RECEIVE_POLL_TIMEOUT_SECONDS) -> float:
    """Return a short receive timeout so cooperative stop is responsive."""
    remaining = snd_loop_timeout(start, duration_seconds=duration_seconds)
    if remaining is None:
        return poll_seconds
    return min(poll_seconds, remaining)


def keepalive_due(now: float, last_keepalive: float, *, sent_setup: bool, interval_seconds: float = KEEPALIVE_INTERVAL_SECONDS) -> bool:
    """Return true when a live SND session should send another keepalive."""
    return sent_setup and (now - last_keepalive) >= interval_seconds


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


async def capture_live_snd(
    config: LiveSndCaptureConfig,
    *,
    allow_live: bool = False,
    stop_event: Event | None = None,
    status_callback: Callable[[dict], None] | None = None,
) -> Path:
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

    async with websockets.connect(
        config.websocket_uri(),
        max_queue=0,
        close_timeout=WEBSOCKET_CLOSE_TIMEOUT_SECONDS,
    ) as websocket:
        auth_command = encode_auth()
        writer.add_tx_cmd(time.monotonic() - start, auth_command)
        await websocket.send(auth_command)

        state = ReceiverState()
        metrics_tracker = SndMetricsTracker()
        sent_ar_ok = False
        sent_setup = False
        last_keepalive = start

        while snd_loop_allowed(start, frames, duration_seconds=config.duration_seconds, max_frames=config.max_frames):
            if stop_event is not None and stop_event.is_set():
                break
            now = time.monotonic()
            if keepalive_due(now, last_keepalive, sent_setup=sent_setup):
                command = encode_keepalive()
                writer.add_tx_cmd(now - start, command)
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
                        if status_callback is not None:
                            frame = parse_snd_uncompressed_mono(payload)
                            status_callback(metrics_tracker.observe(frame, sample_rate=state.sample_rate))
                    continue

            params = parse_msg(text).params
            raise_for_kiwi_error(params, receiver=config.receiver)
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
