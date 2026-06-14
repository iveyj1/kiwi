"""Recording helpers for decoded KiwiSDR audio fixtures."""

from __future__ import annotations

import struct
import wave
from dataclasses import dataclass
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


def write_snd_fixture_wav(fixture_path: str | Path, output_path: str | Path) -> WavRecordingResult:
    """Decode uncompressed mono SND fixture audio into a standard PCM WAV file."""
    fixture_path = Path(fixture_path)
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    state = ReceiverState()
    tracker = SndSequenceTracker()
    pcm = bytearray()
    snd_frames = 0
    sequence_gaps = 0

    for event in load_jsonl_events(fixture_path):
        if event.type == "msg":
            state = state.apply_msg_params(parse_msg(event.raw["text"]).params)
        elif event.type == "binary":
            frame = parse_snd_uncompressed_mono(event.binary_payload)
            status = tracker.observe(frame)
            if status.missing_count:
                sequence_gaps += status.missing_count
            snd_frames += 1
            for sample in frame.samples:
                pcm.extend(struct.pack("<h", sample))

    if state.sample_rate is None:
        raise ValueError(f"fixture has no MSG sample_rate: {fixture_path}")

    sample_rate_hz = int(round(state.sample_rate))
    with wave.open(str(output_path), "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(sample_rate_hz)
        wav.writeframes(bytes(pcm))

    return WavRecordingResult(
        path=output_path,
        sample_rate_hz=sample_rate_hz,
        channels=1,
        sample_width_bytes=2,
        frames=len(pcm) // 2,
        snd_frames=snd_frames,
        sequence_gaps=sequence_gaps,
    )
