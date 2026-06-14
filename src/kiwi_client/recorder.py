"""Recording helpers for decoded KiwiSDR audio fixtures."""

from __future__ import annotations

import argparse
import json
import struct
import wave
from dataclasses import asdict, dataclass
from pathlib import Path

from kiwi_client.audio import SndSequenceTracker
from kiwi_client.fixtures import load_jsonl_events
from kiwi_client.protocol import parse_msg, parse_snd_uncompressed_mono
from kiwi_client.receiver_model import ReceiverState


@dataclass(frozen=True)
class WavRecordingResult:
    """Summary of a fixture-to-WAV recording."""

    path: Path
    sample_rate_hz: int
    channels: int
    sample_width_bytes: int
    frames: int
    snd_frames: int
    sequence_gaps: int


class SndWavRecorder:
    """Accumulate uncompressed mono SND audio and write a WAV file."""

    def __init__(self) -> None:
        self.state = ReceiverState()
        self.tracker = SndSequenceTracker()
        self.pcm = bytearray()
        self.snd_frames = 0
        self.sequence_gaps = 0

    def add_msg(self, text: str) -> None:
        """Apply one Kiwi MSG event to the recording state."""
        self.state = self.state.apply_msg_params(parse_msg(text).params)

    def add_snd_payload(self, payload: bytes) -> None:
        """Decode and append one uncompressed mono SND payload."""
        frame = parse_snd_uncompressed_mono(payload)
        status = self.tracker.observe(frame)
        if status.missing_count:
            self.sequence_gaps += status.missing_count
        self.snd_frames += 1
        for sample in frame.samples:
            self.pcm.extend(struct.pack("<h", sample))

    @property
    def sample_rate_hz(self) -> int:
        """Return rounded integer sample rate for a standard WAV header."""
        if self.state.sample_rate is None:
            raise ValueError("recording has no MSG sample_rate")
        return int(round(self.state.sample_rate))

    def write_wav(self, output_path: str | Path) -> WavRecordingResult:
        """Write accumulated PCM to a standard mono 16-bit WAV file."""
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        sample_rate_hz = self.sample_rate_hz
        with wave.open(str(output_path), "wb") as wav:
            wav.setnchannels(1)
            wav.setsampwidth(2)
            wav.setframerate(sample_rate_hz)
            wav.writeframes(bytes(self.pcm))
        return WavRecordingResult(
            path=output_path,
            sample_rate_hz=sample_rate_hz,
            channels=1,
            sample_width_bytes=2,
            frames=len(self.pcm) // 2,
            snd_frames=self.snd_frames,
            sequence_gaps=self.sequence_gaps,
        )


def write_snd_fixture_wav(fixture_path: str | Path, output_path: str | Path) -> WavRecordingResult:
    """Decode uncompressed mono SND fixture audio into a standard PCM WAV file."""
    recorder = SndWavRecorder()
    for event in load_jsonl_events(fixture_path):
        if event.type == "msg":
            recorder.add_msg(event.raw["text"])
        elif event.type == "binary":
            recorder.add_snd_payload(event.binary_payload)
    return recorder.write_wav(output_path)


def build_arg_parser() -> argparse.ArgumentParser:
    """Build the fixture-to-WAV recorder CLI parser."""
    parser = argparse.ArgumentParser(description="Convert an uncompressed mono SND JSONL fixture to WAV")
    parser.add_argument("fixture", type=Path, help="input KiwiSDR JSONL fixture")
    parser.add_argument("output", type=Path, help="output WAV path")
    parser.add_argument("--json", action="store_true", help="print recording summary as JSON")
    return parser


def main(argv: list[str] | None = None) -> int:
    """CLI entrypoint for fixture-to-WAV recording."""
    parser = build_arg_parser()
    args = parser.parse_args(argv)
    try:
        result = write_snd_fixture_wav(args.fixture, args.output)
    except Exception as exc:
        parser.error(str(exc))
        return 2

    if args.json:
        data = asdict(result)
        data["path"] = str(result.path)
        print(json.dumps(data, indent=2, sort_keys=True))
    else:
        print(result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
