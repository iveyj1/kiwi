"""KiwiSDR waterfall frame parsing and model helpers."""

from __future__ import annotations

import math
import struct
from dataclasses import dataclass, replace

from kiwi_client.protocol import KiwiProtocolError, websocket_tag

WF_HEADER_BYTES = 13
WF_ZOOM_MASK = 0x0000FFFF
SEQ_MODULUS = 2**32
SEQ_REORDER_THRESHOLD = 2**31


@dataclass(frozen=True)
class WaterfallReceiverState:
    """Receiver metadata needed to map W/F bins onto frequency."""

    bandwidth_hz: int | None = None
    center_freq_hz: int | None = None
    wf_fft_size: int | None = None
    wf_fps: int | None = None
    wf_fps_max: int | None = None
    zoom_max: int | None = None
    wf_cal_db: int | None = None
    zoom: int | None = None
    start_bin: int | None = None

    def apply_msg_params(self, params: dict[str, str | None]) -> "WaterfallReceiverState":
        """Return updated state after one Kiwi MSG parameter dictionary."""
        values = {
            "bandwidth_hz": self.bandwidth_hz,
            "center_freq_hz": self.center_freq_hz,
            "wf_fft_size": self.wf_fft_size,
            "wf_fps": self.wf_fps,
            "wf_fps_max": self.wf_fps_max,
            "zoom_max": self.zoom_max,
            "wf_cal_db": self.wf_cal_db,
            "zoom": self.zoom,
            "start_bin": self.start_bin,
        }
        fields = {
            "bandwidth": "bandwidth_hz",
            "center_freq": "center_freq_hz",
            "wf_fft_size": "wf_fft_size",
            "wf_fps": "wf_fps",
            "wf_fps_max": "wf_fps_max",
            "zoom_max": "zoom_max",
            "wf_cal": "wf_cal_db",
            "zoom": "zoom",
            "start": "start_bin",
        }
        for parameter, field in fields.items():
            if params.get(parameter) is not None:
                values[field] = int(params[parameter])
        return WaterfallReceiverState(**values)


@dataclass(frozen=True)
class WaterfallInterpolation:
    """Decoded Kiwi FFT-to-waterfall-bin reduction mode."""

    value: int
    method: str
    cic_compensation: bool


_WF_INTERPOLATION_METHODS = ("max", "min", "last", "drop", "cma")


def decode_waterfall_interpolation(value: int) -> WaterfallInterpolation:
    """Decode categorical `SET interp` values used by the Kiwi W/F server.

    Values 0..4 select max/min/last/drop/CMA reduction. Adding 10 selects
    the same method with CIC passband compensation. This is not a monotonic
    smoothing control.
    """
    cic_compensation = 10 <= value <= 14
    method_index = value - 10 if cic_compensation else value
    if method_index < 0 or method_index >= len(_WF_INTERPOLATION_METHODS):
        raise ValueError("waterfall interp must be one of 0..4 or 10..14")
    return WaterfallInterpolation(
        value=value,
        method=_WF_INTERPOLATION_METHODS[method_index],
        cic_compensation=cic_compensation,
    )


@dataclass(frozen=True)
class WaterfallCursor:
    """An exact selected frequency with independent waterfall-bin resolution."""

    start_khz: float
    end_khz: float
    bin_width_hz: float
    frequency_khz: float

    @classmethod
    def for_span(
        cls,
        *,
        start_khz: float,
        end_khz: float,
        bin_width_hz: float,
        step_hz: float,
        preferred_khz: float | None = None,
    ) -> "WaterfallCursor":
        if end_khz <= start_khz:
            raise ValueError("cursor end_khz must be greater than start_khz")
        if bin_width_hz <= 0:
            raise ValueError("cursor bin_width_hz must be positive")
        if step_hz <= 0:
            raise ValueError("cursor step_hz must be positive")
        target_khz = (start_khz + end_khz) / 2.0 if preferred_khz is None else preferred_khz
        if not math.isfinite(target_khz):
            raise ValueError("cursor preferred_khz must be finite")
        minimum_step = math.ceil(start_khz * 1000.0 / step_hz - 1e-12)
        maximum_step = math.floor(end_khz * 1000.0 / step_hz + 1e-12)
        if minimum_step <= maximum_step:
            selected_step = min(
                max(minimum_step, math.floor(target_khz * 1000.0 / step_hz + 0.5)),
                maximum_step,
            )
            frequency_khz = selected_step * step_hz / 1000.0
        else:
            frequency_khz = min(max(target_khz, start_khz), end_khz)
        return cls(
            start_khz=start_khz,
            end_khz=end_khz,
            bin_width_hz=bin_width_hz,
            frequency_khz=frequency_khz,
        )

    def moved_steps(self, delta: int, *, step_hz: float) -> "WaterfallCursor":
        if step_hz <= 0:
            raise ValueError("cursor step_hz must be positive")
        frequency_hz = self.frequency_khz * 1000.0
        if delta > 0:
            selected_step = math.floor(frequency_hz / step_hz + 1e-12) + delta
        elif delta < 0:
            selected_step = math.ceil(frequency_hz / step_hz - 1e-12) + delta
        else:
            return self
        minimum_step = math.ceil(self.start_khz * 1000.0 / step_hz - 1e-12)
        maximum_step = math.floor(self.end_khz * 1000.0 / step_hz + 1e-12)
        if minimum_step > maximum_step:
            return self
        selected_step = min(max(minimum_step, selected_step), maximum_step)
        return replace(self, frequency_khz=selected_step * step_hz / 1000.0)

    def with_span(self, *, start_khz: float, end_khz: float, bin_width_hz: float) -> "WaterfallCursor":
        if end_khz <= start_khz:
            raise ValueError("cursor end_khz must be greater than start_khz")
        if bin_width_hz <= 0:
            raise ValueError("cursor bin_width_hz must be positive")
        return replace(
            self,
            start_khz=start_khz,
            end_khz=end_khz,
            bin_width_hz=bin_width_hz,
            frequency_khz=min(max(self.frequency_khz, start_khz), end_khz),
        )


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


def contextualize_waterfall_frame(
    frame: WaterfallFrame,
    state: WaterfallReceiverState,
) -> WaterfallFrame:
    """Populate frame frequency fields from W/F metadata and server bin coordinates."""
    required = (state.bandwidth_hz, state.wf_fft_size, state.zoom_max)
    if any(value is None for value in required):
        return frame

    zoom = (
        frame.flags_x_zoom_server & WF_ZOOM_MASK
        if frame.flags_x_zoom_server is not None
        else state.zoom
    )
    start_bin = frame.x_bin_server if frame.x_bin_server is not None else state.start_bin
    if zoom is None or start_bin is None:
        return frame
    assert state.bandwidth_hz is not None
    assert state.wf_fft_size is not None
    assert state.zoom_max is not None
    if zoom < 0 or zoom > state.zoom_max:
        raise ValueError(f"waterfall frame zoom {zoom} exceeds receiver zoom_max {state.zoom_max}")

    max_bins = state.wf_fft_size << state.zoom_max
    bins_at_zoom = state.wf_fft_size << (state.zoom_max - zoom)
    if start_bin < 0 or start_bin + bins_at_zoom > max_bins:
        raise ValueError("waterfall frame start bin is outside receiver bandwidth")

    start_hz = start_bin / max_bins * state.bandwidth_hz
    span_hz = state.bandwidth_hz / (2**zoom)
    return replace(
        frame,
        start_khz=start_hz / 1000.0,
        center_khz=(start_hz + span_hz / 2.0) / 1000.0,
        span_khz=span_hz / 1000.0,
        bin_width_hz=span_hz / len(frame.bins),
    )


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
