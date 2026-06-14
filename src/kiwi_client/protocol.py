"""KiwiSDR protocol parsing primitives."""

from __future__ import annotations

import struct
from dataclasses import dataclass
from urllib.parse import unquote

SND_FLAG_ADC_OVFL = 0x02
SND_FLAG_STEREO = 0x08
SND_FLAG_COMPRESSED = 0x10
SND_FLAG_LITTLE_ENDIAN = 0x80


class KiwiProtocolError(ValueError):
    """Raised when a KiwiSDR frame is malformed or unsupported."""


@dataclass(frozen=True)
class MsgFrame:
    """Decoded KiwiSDR MSG name/value parameters."""

    params: dict[str, str | None]


@dataclass(frozen=True)
class SndAudioFrame:
    """Decoded uncompressed mono SND audio frame."""

    flags: int
    seq: int
    smeter: int
    rssi_db: float
    samples: tuple[int, ...]


def websocket_tag(payload: bytes) -> str:
    """Return the 3-byte KiwiSDR WebSocket message tag."""
    if len(payload) < 3:
        raise KiwiProtocolError("websocket payload is shorter than 3-byte tag")
    return payload[:3].decode("ascii", errors="strict")


def parse_msg(payload: bytes | str) -> MsgFrame:
    """Parse one full WebSocket `MSG` payload into name/value parameters."""
    if isinstance(payload, str):
        payload = payload.encode("utf-8")

    tag = websocket_tag(payload)
    if tag != "MSG":
        raise KiwiProtocolError(f"expected MSG tag, got {tag!r}")

    body = payload[3:]
    if body[:1] in (b" ", b"\x00"):
        body = body[1:]
    text = body.decode("utf-8", errors="strict")

    params: dict[str, str | None] = {}
    for pair in text.split():
        if "=" in pair:
            name, value = pair.split("=", 1)
            params[name] = unquote(value)
        else:
            params[pair] = None
    return MsgFrame(params=params)


def parse_snd_uncompressed_mono(payload: bytes) -> SndAudioFrame:
    """Parse one full WebSocket `SND` payload as uncompressed mono PCM.

    This intentionally supports only the first harness target:
    non-stereo, non-compressed mono audio. Later tests should add compressed
    ADPCM and stereo/IQ paths without changing this fixture-backed behavior.
    """
    tag = websocket_tag(payload)
    if tag != "SND":
        raise KiwiProtocolError(f"expected SND tag, got {tag!r}")

    body = payload[3:]
    if len(body) < 7:
        raise KiwiProtocolError("SND body is shorter than 7-byte header")

    flags, seq = struct.unpack("<BI", body[:5])
    smeter = struct.unpack(">H", body[5:7])[0]
    data = body[7:]

    if flags & SND_FLAG_COMPRESSED:
        raise KiwiProtocolError("compressed SND audio is not supported by this parser")
    if flags & SND_FLAG_STEREO:
        raise KiwiProtocolError("stereo/IQ SND audio is not supported by this parser")
    if len(data) % 2 != 0:
        raise KiwiProtocolError("uncompressed mono SND PCM payload has odd byte count")

    sample_count = len(data) // 2
    samples = struct.unpack(f">{sample_count}h", data) if sample_count else ()
    rssi_db = 0.1 * smeter - 127
    return SndAudioFrame(
        flags=flags,
        seq=seq,
        smeter=smeter,
        rssi_db=rssi_db,
        samples=tuple(samples),
    )
