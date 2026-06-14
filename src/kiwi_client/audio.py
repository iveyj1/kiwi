"""Audio stream helpers that sit above raw SND frame parsing."""

from __future__ import annotations

from dataclasses import dataclass

from kiwi_client.protocol import SND_FLAG_ADC_OVFL, SndAudioFrame

SEQ_MODULUS = 2**32
SEQ_REORDER_THRESHOLD = 2**31


@dataclass(frozen=True)
class SndSequenceStatus:
    """Continuity status for one SND audio frame."""

    seq: int
    expected_seq: int | None
    missing_count: int = 0
    out_of_order: bool = False

    @property
    def ok(self) -> bool:
        """Return true when this frame arrived at the expected sequence."""
        return self.expected_seq is None or (self.missing_count == 0 and not self.out_of_order)


class SndSequenceTracker:
    """Track SND sequence continuity, including uint32 wraparound."""

    def __init__(self) -> None:
        self._expected_seq: int | None = None

    def observe(self, frame: SndAudioFrame) -> SndSequenceStatus:
        """Observe one frame and return continuity status."""
        expected = self._expected_seq
        self._expected_seq = (frame.seq + 1) % SEQ_MODULUS

        if expected is None:
            return SndSequenceStatus(seq=frame.seq, expected_seq=None)

        delta = (frame.seq - expected) % SEQ_MODULUS
        if delta == 0:
            return SndSequenceStatus(seq=frame.seq, expected_seq=expected)
        if delta > SEQ_REORDER_THRESHOLD:
            return SndSequenceStatus(seq=frame.seq, expected_seq=expected, out_of_order=True)
        return SndSequenceStatus(seq=frame.seq, expected_seq=expected, missing_count=delta)


def has_adc_overflow(frame: SndAudioFrame) -> bool:
    """Return true when the SND frame flags report ADC overflow."""
    return bool(frame.flags & SND_FLAG_ADC_OVFL)


class SndMetricsTracker:
    """Track latest SND status metrics for user-facing operation status."""

    def __init__(self) -> None:
        self.sequence = SndSequenceTracker()
        self.snd_frames = 0
        self.sequence_gaps = 0
        self.adc_overflows = 0

    def observe(self, frame: SndAudioFrame, *, sample_rate: float | None = None) -> dict:
        """Observe one SND frame and return a JSON-serializable metrics snapshot."""
        status = self.sequence.observe(frame)
        self.snd_frames += 1
        if status.missing_count:
            self.sequence_gaps += status.missing_count
        if has_adc_overflow(frame):
            self.adc_overflows += 1

        metrics = {
            "smeter": frame.smeter,
            "rssi_db": frame.rssi_db,
            "snd_seq": frame.seq,
            "snd_frames": self.snd_frames,
            "sequence_gaps": self.sequence_gaps,
            "adc_overflows": self.adc_overflows,
        }
        if sample_rate is not None:
            metrics["sample_rate_hz"] = int(round(sample_rate))
        return metrics
