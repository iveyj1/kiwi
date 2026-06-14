"""Guarded live SND audio playback.

The live path can use SoundDeviceSink for real audio, while replay/dry-run tests
use NullAudioSink with no device or network access.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import queue
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from threading import Event
from typing import Any

from kiwi_client.commands import encode_ar_ok, encode_auth, encode_basic_snd_setup
from kiwi_client.live_capture import (
    LOCAL_RECEIVERS,
    MAX_DURATION_SECONDS,
    MAX_FRAMES,
    WEBSOCKET_CLOSE_TIMEOUT_SECONDS,
    LiveCaptureError,
    sorted_receiver_names,
)
from kiwi_client.playback import AudioSink, NullAudioSink, PlaybackResult, SoundDeviceSink, samples_to_pcm16le
from kiwi_client.protocol import parse_msg, parse_snd_uncompressed_mono
from kiwi_client.receiver_model import ReceiverState
from kiwi_client.transport import ReplayTransport


@dataclass(frozen=True)
class LiveSndPlaybackConfig:
    """Configuration for one short guarded SND playback session."""

    host: str = "10.0.0.40"
    port: int = 8073
    user: str = "kiwi-client"
    frequency_khz: float = 5000.0
    mode: str = "am"
    low_cut_hz: int = -5000
    high_cut_hz: int = 5000
    duration_seconds: float = 3.0
    max_frames: int = 20
    compression: bool = False
    timestamp: int | None = None

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
            raise LiveCaptureError("first live playback path must use compression=0")

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


def _commands_after_msg(state: ReceiverState, sent_ar_ok: bool, sent_setup: bool, config: LiveSndPlaybackConfig) -> tuple[list[str], bool, bool]:
    commands: list[str] = []
    if state.audio_rate is not None and not sent_ar_ok:
        commands.append(encode_ar_ok(state.audio_rate))
        sent_ar_ok = True
    if state.sample_rate is not None and sent_ar_ok and not sent_setup:
        commands.extend(config.setup_commands())
        sent_setup = True
    return commands, sent_ar_ok, sent_setup


def _write_snd_to_sink(payload: bytes, sink: AudioSink, state: ReceiverState, sink_started: bool) -> tuple[bool, int, int]:
    frame = parse_snd_uncompressed_mono(payload)
    if state.sample_rate is None:
        raise LiveCaptureError("received SND before MSG sample_rate")
    if not sink_started:
        sink.start(sample_rate_hz=int(round(state.sample_rate)), channels=1, sample_width_bytes=2)
        sink_started = True
    pcm = samples_to_pcm16le(frame.samples)
    sink.write(pcm)
    return sink_started, len(frame.samples), len(pcm)


def play_replay_snd(transport: ReplayTransport, sink: AudioSink, *, config: LiveSndPlaybackConfig, dry_run: bool = True) -> PlaybackResult:
    """Play a strict replayed SND fixture through an AudioSink."""
    state = ReceiverState()
    sink_started = False
    sent_ar_ok = False
    sent_setup = False
    snd_frames = 0
    total_frames = 0
    bytes_written = 0

    transport.send(encode_auth())
    while not transport.done and snd_frames < config.max_frames:
        event = transport.receive()
        if event.type == "msg" and event.text is not None:
            state = state.apply_msg_params(parse_msg(event.text).params)
            commands, sent_ar_ok, sent_setup = _commands_after_msg(state, sent_ar_ok, sent_setup, config)
            for command in commands:
                transport.send(command)
        elif event.type == "binary" and event.payload is not None:
            sink_started, frames, byte_count = _write_snd_to_sink(event.payload, sink, state, sink_started)
            snd_frames += 1
            total_frames += frames
            bytes_written += byte_count
    if sink_started:
        sink.stop()
    return PlaybackResult(
        path=Path("<live-snd>"),
        sample_rate_hz=int(round(state.sample_rate or 0)),
        channels=1,
        sample_width_bytes=2,
        frames=total_frames,
        chunks=snd_frames,
        bytes_written=bytes_written,
        dry_run=dry_run,
    )


async def play_live_snd(
    config: LiveSndPlaybackConfig,
    sink: AudioSink,
    *,
    allow_live: bool = False,
    dry_run: bool = False,
    stop_event: Event | None = None,
    command_queue: queue.Queue[str] | None = None,
) -> PlaybackResult:
    """Run one guarded live SND playback session."""
    config.validate()
    if not allow_live:
        raise LiveCaptureError("live playback requires allow_live=True")
    try:
        import websockets
    except ImportError as exc:
        raise LiveCaptureError("live playback requires optional dependency: pip install '.[live]'") from exc

    state = ReceiverState()
    sink_started = False
    sent_ar_ok = False
    sent_setup = False
    snd_frames = 0
    total_frames = 0
    bytes_written = 0
    start = time.monotonic()

    async with websockets.connect(
        config.websocket_uri(),
        max_queue=0,
        close_timeout=WEBSOCKET_CLOSE_TIMEOUT_SECONDS,
    ) as websocket:
        try:
            await websocket.send(encode_auth())
            while snd_frames < config.max_frames and (time.monotonic() - start) < config.duration_seconds:
                if stop_event is not None and stop_event.is_set():
                    break
                remaining = config.duration_seconds - (time.monotonic() - start)
                if remaining <= 0:
                    break
                if command_queue is not None and sent_setup:
                    while True:
                        try:
                            await websocket.send(command_queue.get_nowait())
                        except queue.Empty:
                            break
                try:
                    message = await asyncio.wait_for(websocket.recv(), timeout=remaining)
                except asyncio.TimeoutError:
                    break
                if isinstance(message, str):
                    state = state.apply_msg_params(parse_msg(message).params)
                else:
                    payload = bytes(message)
                    if payload.startswith(b"MSG"):
                        state = state.apply_msg_params(parse_msg(payload).params)
                    else:
                        sink_started, frames, byte_count = _write_snd_to_sink(payload, sink, state, sink_started)
                        snd_frames += 1
                        total_frames += frames
                        bytes_written += byte_count
                        continue
                commands, sent_ar_ok, sent_setup = _commands_after_msg(state, sent_ar_ok, sent_setup, config)
                for command in commands:
                    await websocket.send(command)
        finally:
            if sink_started:
                sink.stop()
                sink_started = False
    return PlaybackResult(
        path=Path("<live-snd>"),
        sample_rate_hz=int(round(state.sample_rate or 0)),
        channels=1,
        sample_width_bytes=2,
        frames=total_frames,
        chunks=snd_frames,
        bytes_written=bytes_written,
        dry_run=dry_run,
    )


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Guarded short local KiwiSDR SND playback")
    parser.add_argument("--host", default="10.0.0.40", choices=[host for host, _ in sorted(LOCAL_RECEIVERS)])
    parser.add_argument("--port", type=int, default=8073)
    parser.add_argument("--user", default="kiwi-client")
    parser.add_argument("--frequency-khz", type=float, default=5000.0)
    parser.add_argument("--mode", default="am")
    parser.add_argument("--low-cut-hz", type=int, default=-5000)
    parser.add_argument("--high-cut-hz", type=int, default=5000)
    parser.add_argument("--duration-seconds", type=float, default=3.0)
    parser.add_argument("--max-frames", type=int, default=20)
    parser.add_argument("--timestamp", type=int)
    parser.add_argument("--dry-run", action="store_true", help="print playback plan and do not connect")
    parser.add_argument("--null-sink", action="store_true", help="connect live but discard audio instead of using an output device")
    parser.add_argument("--allow-live", action="store_true", help="required to make a live receiver connection")
    parser.add_argument("--json", action="store_true", help="print playback summary as JSON")
    return parser


def config_from_args(args: argparse.Namespace) -> LiveSndPlaybackConfig:
    return LiveSndPlaybackConfig(
        host=args.host,
        port=args.port,
        user=args.user,
        frequency_khz=args.frequency_khz,
        mode=args.mode,
        low_cut_hz=args.low_cut_hz,
        high_cut_hz=args.high_cut_hz,
        duration_seconds=args.duration_seconds,
        max_frames=args.max_frames,
        timestamp=args.timestamp,
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
        sink: AudioSink = NullAudioSink() if args.null_sink else SoundDeviceSink()
        result = asyncio.run(play_live_snd(config, sink, allow_live=True, dry_run=args.null_sink))
        if args.json:
            data = asdict(result)
            data["path"] = str(result.path)
            print(json.dumps(data, indent=2, sort_keys=True))
        else:
            print(result)
        return 0
    except (LiveCaptureError, RuntimeError, ValueError) as exc:
        parser.error(str(exc))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
