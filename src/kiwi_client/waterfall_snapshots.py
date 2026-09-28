"""Bounded renderer-neutral waterfall snapshots for asynchronous frontends."""

from __future__ import annotations

import time
import math
from collections import deque
from dataclasses import dataclass
from threading import Condition
from typing import Callable

from kiwi_client.waterfall import WaterfallFrame


@dataclass(frozen=True)
class WaterfallSnapshotRow:
    """One immutable numeric row with its original frequency mapping."""

    sequence: int
    dbm: tuple[int, ...]
    received_at: float
    start_khz: float | None
    center_khz: float | None
    span_khz: float | None
    bin_width_hz: float | None
    flags_x_zoom_server: int | None


@dataclass(frozen=True)
class WaterfallSnapshot:
    """Latest immutable bounded history published to display consumers."""

    generation: int
    width: int
    max_rows: int
    rows: tuple[WaterfallSnapshotRow, ...]
    current_start_khz: float | None
    current_center_khz: float | None
    current_span_khz: float | None
    current_bin_width_hz: float | None


class WaterfallSnapshotPublisher:
    """Keep bounded numeric rows and coalesce consumers onto the latest state."""

    def __init__(self, *, max_rows: int, clock: Callable[[], float] = time.monotonic) -> None:
        if max_rows <= 0:
            raise ValueError("waterfall snapshot max_rows must be positive")
        self.max_rows = max_rows
        self.clock = clock
        self._condition = Condition()
        self._rows: deque[WaterfallSnapshotRow] = deque(maxlen=max_rows)
        self._width: int | None = None
        self._generation = 0
        self._latest: WaterfallSnapshot | None = None
        self._closed = False
        self._expected_view: tuple[float, int] | None = None

    def expect_view(self, center_khz: float, zoom: int) -> None:
        """Start fresh history and reject queued frames from the old live viewport."""
        with self._condition:
            self._expected_view = (center_khz, zoom)
            self._rows.clear()
            self._latest = None
            # Force incremental raster consumers to rebuild even for the same geometry.
            self._generation += 1
            self._condition.notify_all()

    @property
    def awaiting_view(self) -> bool:
        with self._condition:
            return self._expected_view is not None and self._latest is None and not self._closed

    def _matches_view(self, frame: WaterfallFrame) -> bool:
        if self._expected_view is None:
            return True
        if (frame.flags_x_zoom_server is None or frame.start_khz is None
                or frame.span_khz is None or frame.bin_width_hz is None):
            return False
        center, zoom = self._expected_view
        actual_zoom = frame.flags_x_zoom_server & 0xFFFF
        if actual_zoom != zoom:
            return False
        bandwidth = frame.span_khz * 2 ** actual_zoom
        expected_start = max(0.0, min(center - frame.span_khz / 2, bandwidth - frame.span_khz))
        return math.isclose(frame.start_khz, expected_start, rel_tol=0,
                            abs_tol=max(1e-9, frame.bin_width_hz / 1000))

    def append(self, frame: WaterfallFrame) -> WaterfallSnapshot | None:
        """Publish one frame without retaining superseded snapshot objects."""
        row = tuple(frame.dbm)
        if not row:
            raise ValueError("waterfall snapshot row must not be empty")
        with self._condition:
            if self._closed:
                raise RuntimeError("waterfall snapshot publisher is closed")
            if not self._matches_view(frame):
                return None
            if self._width is None:
                self._width = len(row)
            elif len(row) != self._width:
                raise ValueError(f"waterfall frame width {len(row)} does not match snapshot width {self._width}")
            snapshot_row = WaterfallSnapshotRow(
                sequence=frame.sequence,
                dbm=row,
                received_at=self.clock(),
                start_khz=frame.start_khz,
                center_khz=frame.center_khz,
                span_khz=frame.span_khz,
                bin_width_hz=frame.bin_width_hz,
                flags_x_zoom_server=frame.flags_x_zoom_server,
            )
            self._rows.append(snapshot_row)
            self._generation += 1
            self._latest = WaterfallSnapshot(
                generation=self._generation,
                width=self._width,
                max_rows=self.max_rows,
                rows=tuple(self._rows),
                current_start_khz=frame.start_khz,
                current_center_khz=frame.center_khz,
                current_span_khz=frame.span_khz,
                current_bin_width_hz=frame.bin_width_hz,
            )
            self._condition.notify_all()
            return self._latest

    def latest(self) -> WaterfallSnapshot | None:
        with self._condition:
            return self._latest

    def wait_for_newer(self, generation: int, *, timeout: float | None = None) -> WaterfallSnapshot | None:
        """Return the latest newer snapshot, coalescing skipped generations."""
        with self._condition:
            self._condition.wait_for(
                lambda: self._closed or (self._latest is not None and self._latest.generation > generation),
                timeout=timeout,
            )
            if self._latest is not None and self._latest.generation > generation:
                return self._latest
            return None

    def close(self) -> None:
        with self._condition:
            self._closed = True
            self._condition.notify_all()
