"""Offline helpers for writing KiwiSDR capture fixtures.

This module does not open network connections. It defines the JSONL shape that
future live capture code should use.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from kiwi_client.fixtures import binary_event_payload, fixture_event, write_jsonl_events


@dataclass(frozen=True)
class SndCaptureMetadata:
    """Metadata required for short SND live-to-fixture captures."""

    receiver: str
    utc_time: str
    local_time: str
    frequency_khz: float
    mode: str
    low_cut_hz: int
    high_cut_hz: int
    compression: bool
    notes: str = ""

    def as_fixture_event(self) -> dict[str, Any]:
        """Return this metadata as a fixture meta event."""
        return fixture_event(
            t=0.0,
            dir="meta",
            stream="snd",
            type="capture",
            receiver=self.receiver,
            utc_time=self.utc_time,
            local_time=self.local_time,
            frequency_khz=self.frequency_khz,
            mode=self.mode,
            low_cut_hz=self.low_cut_hz,
            high_cut_hz=self.high_cut_hz,
            compression=self.compression,
            notes=self.notes,
        )


@dataclass(frozen=True)
class WaterfallCaptureMetadata:
    """Metadata required for short W/F live-to-fixture captures."""

    receiver: str
    utc_time: str
    local_time: str
    center_khz: float
    zoom: int
    maxdb: int
    mindb: int
    speed: int
    compression: bool
    notes: str = ""

    def as_fixture_event(self) -> dict[str, Any]:
        """Return this metadata as a fixture meta event."""
        return fixture_event(
            t=0.0,
            dir="meta",
            stream="wf",
            type="capture",
            receiver=self.receiver,
            utc_time=self.utc_time,
            local_time=self.local_time,
            center_khz=self.center_khz,
            zoom=self.zoom,
            maxdb=self.maxdb,
            mindb=self.mindb,
            speed=self.speed,
            compression=self.compression,
            notes=self.notes,
        )


@dataclass
class JsonlCaptureWriter:
    """Accumulate and write KiwiSDR JSONL capture events offline."""

    metadata: Any
    events: list[dict[str, Any]] = field(default_factory=list)

    def __post_init__(self) -> None:
        self.events.append(self.metadata.as_fixture_event())

    def add_tx_cmd(self, t: float, text: str, stream: str = "snd") -> None:
        """Add a transmitted command event."""
        self.events.append(fixture_event(t=t, dir="tx", stream=stream, type="cmd", text=text))

    def add_rx_msg(self, t: float, text: str, stream: str = "snd") -> None:
        """Add a received text MSG event."""
        self.events.append(fixture_event(t=t, dir="rx", stream=stream, type="msg", text=text))

    def add_rx_binary(self, t: float, payload: bytes, stream: str = "snd") -> None:
        """Add a received binary WebSocket payload event."""
        self.events.append(
            fixture_event(
                t=t,
                dir="rx",
                stream=stream,
                type="binary",
                **binary_event_payload(payload),
            )
        )

    def write(self, path: str | Path) -> None:
        """Write the accumulated fixture to a JSONL path."""
        write_jsonl_events(path, self.events)
