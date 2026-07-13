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
from typing import Any, Callable

from kiwi_client.audio import SndMetricsTracker
from kiwi_client.commands import encode_ar_ok, encode_auth, encode_basic_snd_setup, encode_keepalive
from kiwi_client.live_capture import (
    LOCAL_RECEIVERS,
    MAX_DURATION_SECONDS,
    MAX_FRAMES,
    WEBSOCKET_CLOSE_TIMEOUT_SECONDS,
    LiveCaptureError,
    allowed_receiver_names,
    keepalive_due,
    raise_for_kiwi_error,
    receive_poll_timeout,
    snd_loop_allowed,
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
    radio_frequency_khz: float | None = None
    frequency_decimals: int = 3
    mode: str = "am"
    low_cut_hz: int = -5000
    high_cut_hz: int = 5000
    duration_seconds: float = 3.0
    max_frames: int = 20
    compression: bool = False
    startup_mute_ms: int = 300
    startup_fade_in_ms: int = 100
    stop_fade_out_ms: int = 100
    timestamp: int | None = None
    receivers_restricted: bool = True
    allowed_receivers: tuple[str, ...] | None = None

    @property
    def receiver(self) -> str:
        return f"{self.host}:{self.port}"

    def validate(self) -> None:
        if self.receivers_restricted and self.receiver not in allowed_receiver_names(self.allowed_receivers):
            raise LiveCaptureError(f"receiver must be one of the allowed receivers: {allowed_receiver_names(self.allowed_receivers)}")
        if self.duration_seconds < 0:
            raise LiveCaptureError("duration must be >= 0 seconds; 0 means unlimited")
        if self.max_frames < 0:
            raise LiveCaptureError("max_frames must be >= 0; 0 means unlimited")
        if self.compression:
            raise LiveCaptureError("first live playback path must use compression=0")
        if self.startup_mute_ms < 0:
            raise LiveCaptureError("startup_mute_ms must be >= 0")
        if self.startup_fade_in_ms < 0:
            raise LiveCaptureError("startup_fade_in_ms must be >= 0")
        if self.stop_fade_out_ms < 0:
            raise LiveCaptureError("stop_fade_out_ms must be >= 0")

    def websocket_uri(self) -> str:
        timestamp = self.timestamp if self.timestamp is not None else int(time.time())
        return f"ws://{self.host}:{self.port}/{timestamp}/SND"

    @property
    def effective_radio_frequency_khz(self) -> float:
        return self.frequency_khz if self.radio_frequency_khz is None else self.radio_frequency_khz

    def setup_commands(self) -> list[str]:
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
        return {
            "receiver": self.receiver,
            "websocket_uri": self.websocket_uri(),
            "frequency_khz": self.frequency_khz,
            "radio_frequency_khz": self.effective_radio_frequency_khz,
            "frequency_decimals": self.frequency_decimals,
            "mode": self.mode,
            "low_cut_hz": self.low_cut_hz,
            "high_cut_hz": self.high_cut_hz,
            "duration_seconds": self.duration_seconds,
            "max_frames": self.max_frames,
            "compression": self.compression,
            "startup_mute_ms": self.startup_mute_ms,
            "startup_fade_in_ms": self.startup_fade_in_ms,
            "stop_fade_out_ms": self.stop_fade_out_ms,
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


def _write_snd_to_sink(
    payload: bytes,
    sink: AudioSink,
    state: ReceiverState,
    sink_started: bool,
    *,
    startup_drop_samples: int = 0,
    fade_in_remaining: int = 0,
    fade_in_total: int = 0,
    fade_out_remaining: int = 0,
    fade_out_total: int = 0,
    status_callback: Callable[[dict], None] | None = None,
    metrics_tracker: SndMetricsTracker | None = None,
) -> tuple[bool, int, int, int, int, int, bool]:
    frame = parse_snd_uncompressed_mono(payload)
    if state.sample_rate is None:
        raise LiveCaptureError("received SND before MSG sample_rate")
    if status_callback is not None:
        if metrics_tracker is None:
            status_callback({"smeter": frame.smeter, "rssi_db": frame.rssi_db, "snd_seq": frame.seq})
        else:
            status_callback(metrics_tracker.observe(frame, sample_rate=state.sample_rate))

    samples = frame.samples
    if startup_drop_samples:
        drop_count = min(startup_drop_samples, len(samples))
        samples = samples[drop_count:]
        startup_drop_samples -= drop_count
    if samples and fade_in_remaining:
        samples, fade_in_remaining = apply_fade_in(samples, fade_in_remaining=fade_in_remaining, fade_in_total=fade_in_total)
    if samples and fade_out_remaining:
        samples, fade_out_remaining = apply_fade_out(
            samples,
            fade_out_remaining=fade_out_remaining,
            fade_out_total=fade_out_total,
        )
    if not samples:
        return sink_started, 0, 0, startup_drop_samples, fade_in_remaining, fade_out_remaining, False

    if not sink_started:
        sink.start(sample_rate_hz=int(round(state.sample_rate)), channels=1, sample_width_bytes=2)
        sink_started = True
    pcm = samples_to_pcm16le(samples)
    sink.write(pcm)
    return sink_started, len(samples), len(pcm), startup_drop_samples, fade_in_remaining, fade_out_remaining, True


def apply_fade_in(samples: tuple[int, ...], *, fade_in_remaining: int, fade_in_total: int) -> tuple[tuple[int, ...], int]:
    """Apply linear fade-in to leading samples."""
    if fade_in_remaining <= 0 or fade_in_total <= 0:
        return samples, 0
    faded: list[int] = []
    remaining = fade_in_remaining
    for sample in samples:
        if remaining > 0:
            done = fade_in_total - remaining
            gain = max(0.0, min(1.0, done / fade_in_total))
            faded.append(int(sample * gain))
            remaining -= 1
        else:
            faded.append(sample)
    return tuple(faded), remaining


def apply_fade_out(samples: tuple[int, ...], *, fade_out_remaining: int, fade_out_total: int) -> tuple[tuple[int, ...], int]:
    """Apply linear fade-out and truncate after fade completion."""
    if fade_out_remaining <= 0 or fade_out_total <= 0:
        return samples, 0
    faded: list[int] = []
    remaining = fade_out_remaining
    for sample in samples:
        if remaining <= 0:
            break
        gain = max(0.0, min(1.0, remaining / fade_out_total))
        faded.append(int(sample * gain))
        remaining -= 1
    return tuple(faded), remaining


def samples_for_ms(sample_rate: float | None, milliseconds: int) -> int:
    """Return sample count for a duration in ms."""
    if sample_rate is None or milliseconds <= 0:
        return 0
    return int(round(sample_rate * milliseconds / 1000.0))


def startup_drop_samples(config: LiveSndPlaybackConfig, sample_rate: float | None) -> int:
    """Return initial samples to drop for startup mute."""
    return samples_for_ms(sample_rate, config.startup_mute_ms)


def play_replay_snd(
    transport: ReplayTransport,
    sink: AudioSink,
    *,
    config: LiveSndPlaybackConfig,
    dry_run: bool = True,
    status_callback: Callable[[dict], None] | None = None,
) -> PlaybackResult:
    """Play a strict replayed SND fixture through an AudioSink."""
    state = ReceiverState()
    sink_started = False
    sent_ar_ok = False
    sent_setup = False
    snd_frames = 0
    total_frames = 0
    bytes_written = 0
    metrics_tracker = SndMetricsTracker()
    drop_samples_remaining: int | None = None
    fade_in_remaining = 0
    fade_in_total = 0

    transport.send(encode_auth())
    while not transport.done and snd_frames < config.max_frames:
        event = transport.receive()
        if event.type == "msg" and event.text is not None:
            state = state.apply_msg_params(parse_msg(event.text).params)
            commands, sent_ar_ok, sent_setup = _commands_after_msg(state, sent_ar_ok, sent_setup, config)
            for command in commands:
                transport.send(command)
        elif event.type == "binary" and event.payload is not None:
            if drop_samples_remaining is None:
                drop_samples_remaining = startup_drop_samples(config, state.sample_rate)
                fade_in_total = samples_for_ms(state.sample_rate, config.startup_fade_in_ms)
                fade_in_remaining = fade_in_total
            (
                sink_started,
                frames,
                byte_count,
                drop_samples_remaining,
                fade_in_remaining,
                _,
                wrote_chunk,
            ) = _write_snd_to_sink(
                event.payload,
                sink,
                state,
                sink_started,
                startup_drop_samples=drop_samples_remaining,
                fade_in_remaining=fade_in_remaining,
                fade_in_total=fade_in_total,
                status_callback=status_callback,
                metrics_tracker=metrics_tracker,
            )
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
    status_callback: Callable[[dict], None] | None = None,
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
    metrics_tracker = SndMetricsTracker()
    drop_samples_remaining: int | None = None
    fade_in_remaining = 0
    fade_in_total = 0
    fade_out_remaining = 0
    fade_out_total = 0
    fading_out = False
    start = time.monotonic()
    last_keepalive = start

    async with websockets.connect(
        config.websocket_uri(),
        max_queue=0,
        close_timeout=WEBSOCKET_CLOSE_TIMEOUT_SECONDS,
    ) as websocket:
        try:
            await websocket.send(encode_auth())
            while snd_loop_allowed(start, snd_frames, duration_seconds=config.duration_seconds, max_frames=config.max_frames):
                if stop_event is not None and stop_event.is_set() and not fading_out:
                    fade_out_total = samples_for_ms(state.sample_rate, config.stop_fade_out_ms)
                    fade_out_remaining = fade_out_total
                    fading_out = fade_out_total > 0 and sink_started
                    if not fading_out:
                        break
                now = time.monotonic()
                if keepalive_due(now, last_keepalive, sent_setup=sent_setup):
                    await websocket.send(encode_keepalive())
                    last_keepalive = now
                remaining = receive_poll_timeout(start, duration_seconds=config.duration_seconds)
                if remaining == 0:
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
                    continue
                if isinstance(message, str):
                    params = parse_msg(message).params
                    raise_for_kiwi_error(params, receiver=config.receiver)
                    state = state.apply_msg_params(params)
                else:
                    payload = bytes(message)
                    if payload.startswith(b"MSG"):
                        params = parse_msg(payload).params
                        raise_for_kiwi_error(params, receiver=config.receiver)
                        state = state.apply_msg_params(params)
                    else:
                        if drop_samples_remaining is None:
                            drop_samples_remaining = startup_drop_samples(config, state.sample_rate)
                            fade_in_total = samples_for_ms(state.sample_rate, config.startup_fade_in_ms)
                            fade_in_remaining = fade_in_total
                        (
                            sink_started,
                            frames,
                            byte_count,
                            drop_samples_remaining,
                            fade_in_remaining,
                            fade_out_remaining,
                            wrote_chunk,
                        ) = _write_snd_to_sink(
                            payload,
                            sink,
                            state,
                            sink_started,
                            startup_drop_samples=drop_samples_remaining,
                            fade_in_remaining=fade_in_remaining,
                            fade_in_total=fade_in_total,
                            fade_out_remaining=fade_out_remaining,
                            fade_out_total=fade_out_total,
                            status_callback=status_callback,
                            metrics_tracker=metrics_tracker,
                        )
                        snd_frames += 1
                        total_frames += frames
                        bytes_written += byte_count
                        if fading_out and fade_out_remaining <= 0:
                            break
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
    parser.add_argument("--startup-mute-ms", type=int, default=300)
    parser.add_argument("--startup-fade-in-ms", type=int, default=100)
    parser.add_argument("--stop-fade-out-ms", type=int, default=100)
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
        startup_mute_ms=args.startup_mute_ms,
        startup_fade_in_ms=args.startup_fade_in_ms,
        stop_fade_out_ms=args.stop_fade_out_ms,
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
