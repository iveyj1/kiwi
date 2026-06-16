"""KiwiSDR waterfall frame parsing and model helpers."""

from __future__ import annotations

import struct
from dataclasses import dataclass

from kiwi_client.protocol import KiwiProtocolError, websocket_tag

WF_HEADER_BYTES = 13


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
