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
