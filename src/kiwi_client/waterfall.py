"""KiwiSDR waterfall frame parsing and model helpers."""

from __future__ import annotations

import struct
from dataclasses import dataclass, replace

from kiwi_client.protocol import KiwiProtocolError, websocket_tag

WF_HEADER_BYTES = 13
SEQ_MODULUS = 2**32
SEQ_REORDER_THRESHOLD = 2**31

DEFAULT_WF_FFT_SIZE = 1024
DEFAULT_ZOOM_MAX = 14
ZOOM_FLAG_MASK = 0x0F

# Provisional. Known AM carriers peak this many bins below where
# `start_hz + index * bin_width` predicts. Measured across three local captures
# (zoom 8 at 910 kHz, zoom 9 at 760 kHz, zoom 11 at 910 kHz) by parabolic
# interpolation of 17 carrier peaks: mean 0.895 bins, sd 0.192, 95% interval
# 0.803..0.986.
#
# The offset is constant in BINS, not in Hz: the zoom 11 capture has bins 8x
# narrower than zoom 8, and a Hz-constant offset would have shown up there as
# 6.6 bins rather than the observed 1.0.
#
# The cause is still unknown, and an exact whole-bin offset of 1.0 cannot be
# ruled out, because parabolic interpolation in the dB domain carries a
# window-dependent bias comparable to the gap. Any value in 0.75..0.90 puts
# every measured carrier on the same bin, so this choice does not affect bin
# selection, only sub-bin frequency readout. See docs/kiwi-protocol.md.
PROVISIONAL_BIN_CENTER_OFFSET = 0.89


@dataclass(frozen=True)
class WaterfallSequenceStatus:
    """Continuity status for one W/F frame."""

    seq: int
    expected_seq: int | None
    missing_count: int = 0
    out_of_order: bool = False
    repeated_zero: bool = False

    @property
    def ok(self) -> bool:
        """Return true when this frame arrived at the expected sequence or sequence is inactive."""
        return self.expected_seq is None or self.repeated_zero or (self.missing_count == 0 and not self.out_of_order)


@dataclass(frozen=True)
class WaterfallFrame:
    """Decoded uncompressed KiwiSDR W/F frame."""

    sequence: int
    bins: tuple[int, ...]
    dbm: tuple[int, ...]
    center_khz: float | None = None
    span_khz: float | None = None
    start_khz: float | None = None
    bin_width_hz: float | None = None
    x_bin_server: int | None = None
    flags_x_zoom_server: int | None = None
    raw_flags: int | None = None


@dataclass(frozen=True)
class WaterfallSpan:
    """Receiver W/F geometry needed to map bin indices onto frequencies.

    The values come from `MSG` frames, not from the W/F frame itself, so this is
    kept separate from `WaterfallFrame` and combined with it by `apply_span()`.

    Two different notions of frequency live here, and they differ by
    `bin_center_offset`:

    - Window geometry (`start_hz`, `span_hz`, `center_hz`) describes the tuned
      window as the receiver reports it. No offset is applied; `center_hz`
      reproduces the `cf` value sent in `SET zoom=<z> cf=<khz>`.
    - `bin_frequency_hz()` describes where a signal appearing in a given bin
      actually sits, and does apply the provisional offset.
    """

    bandwidth_hz: float
    zoom: int
    fft_size: int = DEFAULT_WF_FFT_SIZE
    zoom_max: int = DEFAULT_ZOOM_MAX
    bin_center_offset: float = PROVISIONAL_BIN_CENTER_OFFSET

    def __post_init__(self) -> None:
        if self.bandwidth_hz <= 0:
            raise ValueError("waterfall bandwidth must be positive")
        if self.fft_size < 1:
            raise ValueError("waterfall FFT size must be >= 1")
        if self.zoom < 0:
            raise ValueError("waterfall zoom must be >= 0")
        if self.zoom > self.zoom_max:
            raise ValueError(f"waterfall zoom {self.zoom} exceeds zoom_max {self.zoom_max}")

    @property
    def unit_hz(self) -> float:
        """Frequency step of one `x_bin_server` / `MSG start` count."""
        return self.bandwidth_hz / (self.fft_size * 2**self.zoom_max)

    @property
    def bin_width_hz(self) -> float:
        """Width of one displayed W/F bin at this zoom."""
        return self.bandwidth_hz / (self.fft_size * 2**self.zoom)

    @property
    def span_hz(self) -> float:
        """Total frequency span covered by one W/F frame at this zoom."""
        return self.bandwidth_hz / 2**self.zoom

    def start_hz(self, x_bin_server: int) -> float:
        """Return the low-frequency edge of the window for this frame."""
        return x_bin_server * self.unit_hz

    def center_hz(self, x_bin_server: int) -> float:
        """Return the window center, matching the `cf` value that was tuned."""
        return self.start_hz(x_bin_server) + (self.fft_size / 2) * self.bin_width_hz

    def bin_frequency_hz(self, x_bin_server: int, index: int) -> float:
        """Return the calibrated signal frequency for one bin index."""
        return self.start_hz(x_bin_server) + (index + self.bin_center_offset) * self.bin_width_hz

    def bin_for_frequency(self, x_bin_server: int, frequency_hz: float) -> float:
        """Return the fractional bin index a frequency falls at; inverse of `bin_frequency_hz()`."""
        offset_hz = frequency_hz - self.start_hz(x_bin_server)
        return offset_hz / self.bin_width_hz - self.bin_center_offset


class WaterfallSessionMetadata:
    """Accumulate W/F geometry from `MSG` frames across a session.

    The receiver spreads the needed fields over several messages, so parameters
    are folded in as they arrive and `span()` returns `None` until enough is
    known.
    """

    def __init__(self) -> None:
        self.bandwidth_hz: float | None = None
        self.fft_size: int = DEFAULT_WF_FFT_SIZE
        self.zoom_max: int = DEFAULT_ZOOM_MAX
        self.zoom: int | None = None
        self.start: int | None = None

    def observe(self, params: dict[str, str | None]) -> None:
        """Fold one parsed `MSG` parameter mapping into the accumulated geometry."""
        if params.get("bandwidth") is not None:
            self.bandwidth_hz = float(params["bandwidth"])
        if params.get("wf_fft_size") is not None:
            self.fft_size = int(params["wf_fft_size"])
        if params.get("zoom_max") is not None:
            self.zoom_max = int(params["zoom_max"])
        if params.get("zoom") is not None:
            self.zoom = int(params["zoom"])
        if params.get("start") is not None:
            self.start = int(params["start"])

    def span(self) -> WaterfallSpan | None:
        """Return the current span, or `None` while geometry is still incomplete."""
        if self.bandwidth_hz is None or self.zoom is None:
            return None
        return WaterfallSpan(
            bandwidth_hz=self.bandwidth_hz,
            zoom=self.zoom,
            fft_size=self.fft_size,
            zoom_max=self.zoom_max,
        )


def zoom_from_flags(flags_x_zoom_server: int) -> int:
    """Return the zoom level encoded in the low bits of `flags_x_zoom_server`.

    Provisional: only two local observations exist, `8` at zoom 8 and `0x40009`
    at zoom 9, so the exact mask width is unconfirmed. Prefer `MSG zoom=` when
    it is available.
    """
    return flags_x_zoom_server & ZOOM_FLAG_MASK


def apply_span(frame: WaterfallFrame, span: WaterfallSpan) -> WaterfallFrame:
    """Return a copy of `frame` with its frequency fields filled in from `span`."""
    if frame.x_bin_server is None:
        raise ValueError("frame has no x_bin_server; cannot map bins to frequencies")
    start_hz = span.start_hz(frame.x_bin_server)
    return replace(
        frame,
        start_khz=start_hz / 1000.0,
        span_khz=span.span_hz / 1000.0,
        center_khz=span.center_hz(frame.x_bin_server) / 1000.0,
        bin_width_hz=span.bin_width_hz,
    )


class WaterfallSequenceTracker:
    """Track W/F sequence continuity, including uint32 wraparound."""

    def __init__(self) -> None:
        self._expected_seq: int | None = None

    def observe(self, frame: WaterfallFrame) -> WaterfallSequenceStatus:
        """Observe one frame and return continuity status."""
        expected = self._expected_seq
        self._expected_seq = (frame.sequence + 1) % SEQ_MODULUS

        if expected is None:
            return WaterfallSequenceStatus(seq=frame.sequence, expected_seq=None)

        delta = (frame.sequence - expected) % SEQ_MODULUS
        if delta == 0:
            return WaterfallSequenceStatus(seq=frame.sequence, expected_seq=expected)
        if expected == 1 and frame.sequence == 0:
            return WaterfallSequenceStatus(seq=frame.sequence, expected_seq=expected, repeated_zero=True)
        if delta > SEQ_REORDER_THRESHOLD:
            return WaterfallSequenceStatus(seq=frame.sequence, expected_seq=expected, out_of_order=True)
        return WaterfallSequenceStatus(seq=frame.sequence, expected_seq=expected, missing_count=delta)


def raw_sample_to_dbm(sample: int) -> int:
    """Convert one raw W/F byte to reference-style uncalibrated dBm."""
    if sample < 0 or sample > 255:
        raise ValueError("raw waterfall sample must be in range 0..255")
    return sample - 255


def parse_waterfall_uncompressed(payload: bytes) -> WaterfallFrame:
    """Parse one full WebSocket `W/F` payload as uncompressed waterfall bins.

    This intentionally supports the first fixture target only: an uncompressed
    W/F message with the 3-byte tag, one separator/flags byte, a 12-byte
    little-endian W/F header, and raw uint8 bins.
    """
    tag = websocket_tag(payload)
    if tag != "W/F":
        raise KiwiProtocolError(f"expected W/F tag, got {tag!r}")
    if len(payload) < 3 + WF_HEADER_BYTES:
        raise KiwiProtocolError("W/F payload is shorter than 13-byte body header")

    body = payload[3:]
    raw_flags = body[0]
    x_bin_server, flags_x_zoom_server, sequence = struct.unpack("<III", body[1:13])
    bins = tuple(body[13:])
    if not bins:
        raise KiwiProtocolError("W/F frame contains no bin data")

    return WaterfallFrame(
        sequence=sequence,
        bins=bins,
        dbm=tuple(raw_sample_to_dbm(sample) for sample in bins),
        x_bin_server=x_bin_server,
        flags_x_zoom_server=flags_x_zoom_server,
        raw_flags=raw_flags,
    )
