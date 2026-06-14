"""Audio playback scaffolding.

The first playback milestone is deliberately device-free: a WAV reader feeds an
AudioSink interface, and NullAudioSink records stats for tests/dry-runs. A real
audio-device sink can be added behind the same interface later.
"""

from __future__ import annotations

import argparse
import json
import wave
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Protocol


class AudioSink(Protocol):
    """Minimal sink interface for PCM audio playback."""

    def start(self, *, sample_rate_hz: int, channels: int, sample_width_bytes: int) -> None: ...

    def write(self, pcm: bytes) -> None: ...

    def stop(self) -> None: ...


@dataclass(frozen=True)
class PlaybackResult:
    """Summary of WAV playback/dry-run."""

    path: Path
    sample_rate_hz: int
    channels: int
    sample_width_bytes: int
    frames: int
    chunks: int
    bytes_written: int
    dry_run: bool


class NullAudioSink:
    """Audio sink that discards audio but records playback statistics."""

    def __init__(self) -> None:
        self.sample_rate_hz: int | None = None
        self.channels: int | None = None
        self.sample_width_bytes: int | None = None
        self.chunks = 0
        self.bytes_written = 0
        self.started = False
        self.stopped = False

    def start(self, *, sample_rate_hz: int, channels: int, sample_width_bytes: int) -> None:
        self.sample_rate_hz = sample_rate_hz
        self.channels = channels
        self.sample_width_bytes = sample_width_bytes
        self.started = True

    def write(self, pcm: bytes) -> None:
        if not self.started:
            raise RuntimeError("sink has not been started")
        self.chunks += 1
        self.bytes_written += len(pcm)

    def stop(self) -> None:
        self.stopped = True


def play_wav_file(path: str | Path, sink: AudioSink, *, chunk_frames: int = 1024, dry_run: bool = True) -> PlaybackResult:
    """Feed WAV file frames to an audio sink."""
    path = Path(path)
    chunks = 0
    bytes_written = 0
    with wave.open(str(path), "rb") as wav:
        sample_rate_hz = wav.getframerate()
        channels = wav.getnchannels()
        sample_width_bytes = wav.getsampwidth()
        frames = wav.getnframes()
        sink.start(
            sample_rate_hz=sample_rate_hz,
            channels=channels,
            sample_width_bytes=sample_width_bytes,
        )
        while True:
            data = wav.readframes(chunk_frames)
            if not data:
                break
            sink.write(data)
            chunks += 1
            bytes_written += len(data)
        sink.stop()
    return PlaybackResult(
        path=path,
        sample_rate_hz=sample_rate_hz,
        channels=channels,
        sample_width_bytes=sample_width_bytes,
        frames=frames,
        chunks=chunks,
        bytes_written=bytes_written,
        dry_run=dry_run,
    )


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Playback/dry-run a WAV recording")
    parser.add_argument("wav", type=Path)
    parser.add_argument("--chunk-frames", type=int, default=1024)
    parser.add_argument("--dry-run", action="store_true", help="use NullAudioSink; currently required")
    parser.add_argument("--json", action="store_true", help="print playback summary as JSON")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_arg_parser()
    args = parser.parse_args(argv)
    if not args.dry_run:
        parser.error("real audio output is not implemented yet; use --dry-run")
        return 2
    result = play_wav_file(args.wav, NullAudioSink(), chunk_frames=args.chunk_frames, dry_run=True)
    if args.json:
        data = asdict(result)
        data["path"] = str(result.path)
        print(json.dumps(data, indent=2, sort_keys=True))
    else:
        print(result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
