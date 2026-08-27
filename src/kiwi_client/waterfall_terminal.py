"""Standalone raster waterfall viewer using the Kitty graphics protocol."""

from __future__ import annotations

import argparse
import asyncio
import base64
import json
import math
import os
import queue
import shutil
import sys
import tempfile
import termios
import time
import tty
from dataclasses import dataclass
from pathlib import Path
from threading import Event, Lock
from typing import Any, BinaryIO, Callable, Mapping, Protocol

from kiwi_client.commands import encode_waterfall_view
from kiwi_client.config import KiwiClientConfig, discover_config_path, load_config
from kiwi_client.fixtures import load_jsonl_events
from kiwi_client.live_capture import LiveCaptureError
from kiwi_client.live_waterfall import LiveWaterfallCaptureConfig, capture_live_waterfall
from kiwi_client.protocol import parse_msg
from kiwi_client.waterfall import (
    WaterfallCursor,
    WaterfallFrame,
    WF_ZOOM_MASK,
    WaterfallReceiverState,
    contextualize_waterfall_frame,
    parse_waterfall_uncompressed,
)
from kiwi_client.waterfall_raster import (
    RasterImage,
    WaterfallHistory,
    WaterfallOverlay,
    apply_frequency_overlay,
    encode_png,
    render_dbm_rows,
)


@dataclass(frozen=True)
class CursorAction:
    """One decoded local-only cursor control action."""

    kind: str
    bins: int = 0


class CursorKeyDecoder:
    """Incrementally decode cursor keys without assuming one read per escape sequence."""

    _sequences = {
        b"\x1b[1;2D": CursorAction("move-small", -1),
        b"\x1b[1;2C": CursorAction("move-small", 1),
        b"\x1b[D": CursorAction("move", -1),
        b"\x1b[C": CursorAction("move", 1),
    }
    _single = {
        ord("h"): CursorAction("move", -1),
        ord("l"): CursorAction("move", 1),
        ord("H"): CursorAction("move-small", -1),
        ord("L"): CursorAction("move-small", 1),
        ord("t"): CursorAction("cycle-step", 1),
        ord("T"): CursorAction("cycle-step", -1),
        ord("0"): CursorAction("reset"),
        ord("c"): CursorAction("recenter"),
        ord("+"): CursorAction("zoom", 1),
        ord("="): CursorAction("zoom", 1),
        ord("-"): CursorAction("zoom", -1),
        ord("q"): CursorAction("quit"),
    }

    def __init__(self) -> None:
        self._buffer = bytearray()

    def feed(self, data: bytes) -> tuple[CursorAction, ...]:
        self._buffer.extend(data)
        actions: list[CursorAction] = []
        while self._buffer:
            raw = bytes(self._buffer)
            matched = next(
                ((sequence, action) for sequence, action in self._sequences.items() if raw.startswith(sequence)),
                None,
            )
            if matched is not None:
                sequence, action = matched
                del self._buffer[:len(sequence)]
                actions.append(action)
                continue
            if any(sequence.startswith(raw) for sequence in self._sequences):
                break
            action = self._single.get(self._buffer[0])
            del self._buffer[0]
            if action is not None:
                actions.append(action)
        return tuple(actions)


@dataclass(frozen=True)
class FrequencyTick:
    """One non-overlapping frequency label placed on a terminal ruler."""

    frequency_khz: float
    label: str
    label_start: int
    label_stop: int
    edge: bool = False


def choose_frequency_tick_step(raw_step_khz: float) -> float:
    """Round a requested interval up to a 1/2/5 × power-of-ten step."""
    if raw_step_khz <= 0:
        raise ValueError("frequency tick step must be positive")
    exponent = math.floor(math.log10(raw_step_khz))
    magnitude = 10.0**exponent
    fraction = raw_step_khz / magnitude
    if fraction <= 1.0:
        nice = 1.0
    elif fraction <= 2.0:
        nice = 2.0
    elif fraction <= 5.0:
        nice = 5.0
    else:
        nice = 10.0
    return nice * magnitude


def frequency_label_decimals(step_khz: float) -> int:
    """Return fixed decimal precision appropriate for one major interval."""
    if step_khz <= 0:
        raise ValueError("frequency tick step must be positive")
    return max(0, min(6, int(math.ceil(-math.log10(step_khz) - 1e-12))))


def _format_frequency_label(frequency_khz: float, decimals: int, *, edge: bool) -> str:
    label_decimals = min(6, decimals + 1) if edge else decimals
    number = f"{frequency_khz:.{label_decimals}f}"
    if edge and "." in number:
        number = number.rstrip("0").rstrip(".")
    return f"{number} kHz"


def frequency_ticks(
    start_khz: float,
    end_khz: float,
    *,
    columns: int,
    columns_per_tick: int = 18,
) -> tuple[FrequencyTick, ...]:
    """Choose and place adaptive, non-overlapping major frequency labels."""
    if columns <= 0:
        raise ValueError("frequency ruler columns must be positive")
    if end_khz <= start_khz:
        raise ValueError("frequency ruler end must be greater than start")
    if columns_per_tick < 8:
        raise ValueError("frequency ruler columns_per_tick must be at least 8")

    span_khz = end_khz - start_khz
    target_labels = max(2, columns // columns_per_tick)
    step_khz = choose_frequency_tick_step(span_khz / (target_labels - 1))
    decimals = frequency_label_decimals(step_khz)

    first_major = math.ceil((start_khz - step_khz * 1e-12) / step_khz) * step_khz
    frequencies = [start_khz]
    frequency = first_major
    while frequency < end_khz - step_khz * 1e-9:
        if frequency > start_khz + step_khz * 1e-9:
            frequencies.append(round(frequency, 12))
        frequency += step_khz
    frequencies.append(end_khz)

    candidates: list[FrequencyTick] = []
    for index, frequency_khz in enumerate(frequencies):
        edge = index == 0 or index == len(frequencies) - 1
        label = _format_frequency_label(frequency_khz, decimals, edge=edge)
        if len(label) > columns:
            label = label[:columns]
        if index == 0:
            label_start = 0
        elif index == len(frequencies) - 1:
            label_start = columns - len(label)
        else:
            position = round((frequency_khz - start_khz) / span_khz * (columns - 1))
            label_start = min(max(0, position - len(label) // 2), columns - len(label))
        candidates.append(
            FrequencyTick(
                frequency_khz=frequency_khz,
                label=label,
                label_start=label_start,
                label_stop=label_start + len(label),
                edge=edge,
            )
        )

    accepted: list[FrequencyTick] = [candidates[0]]
    right_edge = candidates[-1]
    for candidate in candidates[1:-1]:
        if candidate.label_start >= accepted[-1].label_stop + 1 and candidate.label_stop + 1 <= right_edge.label_start:
            accepted.append(candidate)
    if right_edge.label_start >= accepted[-1].label_stop:
        accepted.append(right_edge)
    else:
        accepted = [candidates[0], right_edge] if candidates[0].label_stop <= right_edge.label_start else [candidates[0]]
    return tuple(accepted)


def format_frequency_ruler(
    start_khz: float,
    end_khz: float,
    *,
    columns: int,
    columns_per_tick: int = 18,
) -> str:
    """Render adaptive major frequency labels into one fixed-width terminal row."""
    ruler = [" "] * columns
    for tick in frequency_ticks(
        start_khz,
        end_khz,
        columns=columns,
        columns_per_tick=columns_per_tick,
    ):
        ruler[tick.label_start:tick.label_stop] = tick.label
    return "".join(ruler)


class RasterBackend(Protocol):
    """Display target for rendered waterfall images."""

    def draw(self, image: RasterImage) -> None:
        """Draw or replace one image."""


def terminal_supports_kitty(environ: Mapping[str, str] | None = None) -> bool:
    """Conservatively identify terminals known to support Kitty graphics."""
    values = os.environ if environ is None else environ
    if values.get("KITTY_WINDOW_ID"):
        return True
    identity = " ".join((values.get("TERM", ""), values.get("TERM_PROGRAM", ""))).lower()
    return any(name in identity for name in ("kitty", "ghostty", "wezterm"))


def default_terminal_placement(*, columns: int, lines: int) -> tuple[int, int]:
    """Return a useful default placement: full terminal width and half height."""
    return (max(1, columns), max(1, lines // 2))


def encode_kitty_image(
    png: bytes,
    *,
    image_id: int = 1,
    placement_id: int = 1,
    columns: int | None = None,
    rows: int | None = None,
    chunk_size: int = 4096,
) -> bytes:
    """Encode PNG bytes as chunked Kitty graphics protocol escape sequences."""
    if not png:
        raise ValueError("Kitty image payload must not be empty")
    if image_id <= 0:
        raise ValueError("Kitty image id must be positive")
    if placement_id <= 0:
        raise ValueError("Kitty placement id must be positive")
    if chunk_size <= 0:
        raise ValueError("Kitty chunk size must be positive")
    if columns is not None and columns <= 0:
        raise ValueError("Kitty display columns must be positive")
    if rows is not None and rows <= 0:
        raise ValueError("Kitty display rows must be positive")

    encoded = base64.b64encode(png)
    chunks = [encoded[offset:offset + chunk_size] for offset in range(0, len(encoded), chunk_size)]
    result = bytearray()
    for index, chunk in enumerate(chunks):
        more = 1 if index < len(chunks) - 1 else 0
        if index == 0:
            # q=2 prevents terminal acknowledgements from being echoed by the
            # shell's line discipline. C=1 prevents each update from moving the
            # cursor, and p keeps replacement updates on one stable placement.
            controls = ["a=T", "f=100", "t=d", f"i={image_id}", f"p={placement_id}", "q=2", "C=1"]
            if columns is not None:
                controls.append(f"c={columns}")
            if rows is not None:
                controls.append(f"r={rows}")
            controls.append(f"m={more}")
        else:
            controls = [f"m={more}"]
        result.extend(b"\x1b_G")
        result.extend(",".join(controls).encode("ascii"))
        result.extend(b";")
        result.extend(chunk)
        result.extend(b"\x1b\\")
    return bytes(result)


class KittyTerminalBackend:
    """Raster backend that replaces a stable Kitty terminal image id."""

    def __init__(
        self,
        *,
        output: BinaryIO,
        image_id: int = 1,
        placement_id: int = 1,
        columns: int | None = None,
        rows: int | None = None,
        label_columns_per_tick: int = 18,
        force: bool = False,
        environ: Mapping[str, str] | None = None,
    ) -> None:
        if label_columns_per_tick < 8:
            raise ValueError("frequency ruler label_columns_per_tick must be at least 8")
        self.output = output
        self.image_id = image_id
        self.placement_id = placement_id
        self.columns = columns
        self.rows = rows
        self.label_columns_per_tick = label_columns_per_tick
        self.force = force
        self.environ = os.environ if environ is None else environ
        self._area_reserved = False
        self._finished = False
        self._frequency_ruler: str | None = None
        self._status_line: str | None = None

    def set_status_line(self, status: str) -> None:
        """Set or update a terminal-text status row above the frequency ruler."""
        if self.columns is None:
            return
        line = status[:self.columns].ljust(self.columns)
        if line == self._status_line:
            return
        self._status_line = line
        if self._area_reserved:
            rows_up = 2 if self._frequency_ruler is not None else 1
            self.output.write(f"\x1b[{rows_up}A\r\x1b[2K".encode("ascii"))
            self.output.write(line.encode("ascii"))
            self.output.write(f"\x1b[{rows_up}B\r".encode("ascii"))

    def set_frequency_range(self, start_khz: float, end_khz: float) -> None:
        """Set or update the terminal-text frequency ruler above the image."""
        if self.columns is None:
            return
        ruler = format_frequency_ruler(
            start_khz,
            end_khz,
            columns=self.columns,
            columns_per_tick=self.label_columns_per_tick,
        )
        if ruler == self._frequency_ruler:
            return
        self._frequency_ruler = ruler
        if self._area_reserved:
            self.output.write(b"\x1b[1A\r\x1b[2K")
            self.output.write(ruler.encode("ascii"))
            self.output.write(b"\x1b[1B\r")

    def _reserve_visible_area(self) -> None:
        if self._area_reserved or self.rows is None:
            return
        # The command normally starts on the shell's last visible line. Reserve
        # the placement rectangle, then return to its top-left cell. Without
        # this, C=1 correctly fixes the cursor but leaves the image clipped below
        # the viewport until the shell scrolls during process exit.
        if self._status_line is not None:
            self.output.write(b"\r\x1b[2K")
            self.output.write(self._status_line.encode("ascii"))
            self.output.write(b"\n")
        if self._frequency_ruler is not None:
            self.output.write(b"\r\x1b[2K")
            self.output.write(self._frequency_ruler.encode("ascii"))
            self.output.write(b"\n")
        self.output.write(b"\n" * self.rows)
        self.output.write(f"\x1b[{self.rows}A\r".encode("ascii"))
        self._area_reserved = True

    def draw(self, image: RasterImage) -> None:
        if not self.force and not terminal_supports_kitty(self.environ):
            raise RuntimeError("terminal does not advertise Kitty graphics support; use --force only if support is known")
        self._reserve_visible_area()
        self.output.write(
            encode_kitty_image(
                encode_png(image),
                image_id=self.image_id,
                placement_id=self.placement_id,
                columns=self.columns,
                rows=self.rows,
            )
        )
        flush = getattr(self.output, "flush", None)
        if flush is not None:
            flush()

    def finish(self) -> None:
        """Restore the cursor immediately below a reserved image rectangle."""
        if self._finished:
            return
        if self._area_reserved and self.rows is not None:
            self.output.write(f"\x1b[{self.rows}B\r".encode("ascii"))
            flush = getattr(self.output, "flush", None)
            if flush is not None:
                flush()
        self._finished = True


class WaterfallTerminalViewer:
    """Accumulate parsed W/F frames and render a fixed-height raster history."""

    def __init__(
        self,
        *,
        backend: RasterBackend,
        max_rows: int = 100,
        min_dbm: int | float = -100,
        max_dbm: int | float = -40,
        newest_at_top: bool = False,
        refresh_hz: float = 5.0,
        tuned_khz: float | None = None,
        low_cut_hz: int | None = None,
        high_cut_hz: int | None = None,
        show_tuned_marker: bool = True,
        show_passband: bool = False,
        show_cursor: bool = False,
        cursor_khz: float | None = None,
        mode: str = "am",
        step_pairs_hz: tuple[tuple[float, float], ...] = ((1000.0, 100.0),),
        step_pair_index: int = 0,
        zoom: int = 0,
        zoom_max: int = 14,
        keyboard_enabled: bool = False,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        if max_dbm <= min_dbm:
            raise ValueError("render max dB must be greater than render min dB")
        if refresh_hz <= 0:
            raise ValueError("refresh_hz must be positive")
        if low_cut_hz is not None and high_cut_hz is not None and high_cut_hz <= low_cut_hz:
            raise ValueError("high_cut_hz must be greater than low_cut_hz")
        if not step_pairs_hz or any(main <= 0 or small <= 0 for main, small in step_pairs_hz):
            raise ValueError("cursor step pairs must contain positive main/small steps")
        if zoom < 0 or zoom_max < zoom:
            raise ValueError("waterfall zoom must satisfy 0 <= zoom <= zoom_max")
        self.backend = backend
        self.history = WaterfallHistory(max_rows=max_rows)
        self.min_dbm = min_dbm
        self.max_dbm = max_dbm
        self.newest_at_top = newest_at_top
        self.tuned_khz = tuned_khz
        self.low_cut_hz = low_cut_hz
        self.high_cut_hz = high_cut_hz
        self.show_tuned_marker = show_tuned_marker
        self.show_passband = show_passband
        self.show_cursor = show_cursor
        self.initial_cursor_khz = cursor_khz
        self.mode = mode.lower()
        self.step_pairs_hz = tuple((float(main), float(small)) for main, small in step_pairs_hz)
        self.step_pair_index = step_pair_index % len(self.step_pairs_hz)
        self.zoom = zoom
        self.zoom_max = zoom_max
        self.keyboard_enabled = keyboard_enabled
        self.refresh_interval = 1.0 / refresh_hz
        self.clock = clock
        self._last_draw: float | None = None
        self._frequency_range: tuple[float, float] | None = None
        self._cursor: WaterfallCursor | None = None
        self._lock = Lock()
        self._generation = 0
        self._drawn_generation = 0

    @property
    def needs_draw(self) -> bool:
        """Return whether newer history exists than the last completed draw."""
        with self._lock:
            return self._generation > self._drawn_generation

    @property
    def cursor_frequency_khz(self) -> float | None:
        with self._lock:
            return None if self._cursor is None else self._cursor.frequency_khz

    @staticmethod
    def _format_cursor_status(
        cursor: WaterfallCursor | None,
        tuned_khz: float | None,
        *,
        mode: str,
        main_step_hz: float,
        small_step_hz: float,
        keyboard_enabled: bool,
    ) -> str | None:
        if cursor is None:
            return None
        parts = [
            f"Cursor {cursor.frequency_khz:.4f} kHz",
            f"{mode} step {main_step_hz:g}/{small_step_hz:g} Hz",
            f"resolution {cursor.bin_width_hz:.3f} Hz",
        ]
        if tuned_khz is not None:
            parts.insert(1, f"tuned {cursor.frequency_khz - tuned_khz:+.3f} kHz")
        if keyboard_enabled:
            parts.append("h/l main H/L small t/T pair c center +/- zoom 0 reset q quit")
        return " | ".join(parts)

    def cursor_status(self) -> str:
        with self._lock:
            main_step_hz, small_step_hz = self.step_pairs_hz[self.step_pair_index]
            return self._format_cursor_status(
                self._cursor,
                self.tuned_khz,
                mode=self.mode,
                main_step_hz=main_step_hz,
                small_step_hz=small_step_hz,
                keyboard_enabled=self.keyboard_enabled,
            ) or ""

    def move_cursor_steps(self, delta: int, *, small: bool = False) -> bool:
        with self._lock:
            if self._cursor is None:
                return False
            main_step_hz, small_step_hz = self.step_pairs_hz[self.step_pair_index]
            cursor = self._cursor.moved_steps(
                delta,
                step_hz=small_step_hz if small else main_step_hz,
            )
            if cursor == self._cursor:
                return False
            self._cursor = cursor
            self._generation += 1
            return True

    def cycle_step_pair(self, delta: int) -> bool:
        with self._lock:
            index = (self.step_pair_index + delta) % len(self.step_pairs_hz)
            if index == self.step_pair_index:
                return False
            self.step_pair_index = index
            self._generation += 1
            return True

    def recenter_command(self) -> str | None:
        with self._lock:
            if self._cursor is None:
                return None
            return encode_waterfall_view(self.zoom, self._cursor.frequency_khz, frequency_decimals=4)

    def zoom_command(self, delta: int) -> str | None:
        with self._lock:
            if self._cursor is None:
                return None
            zoom = min(max(0, self.zoom + delta), self.zoom_max)
            if zoom == self.zoom:
                return None
            self.zoom = zoom
            return encode_waterfall_view(zoom, self._cursor.frequency_khz, frequency_decimals=4)

    def reset_cursor(self) -> bool:
        with self._lock:
            if self._cursor is None:
                return False
            preferred_khz = self.tuned_khz
            main_step_hz, _small_step_hz = self.step_pairs_hz[self.step_pair_index]
            cursor = WaterfallCursor.for_span(
                start_khz=self._cursor.start_khz,
                end_khz=self._cursor.end_khz,
                bin_width_hz=self._cursor.bin_width_hz,
                step_hz=main_step_hz,
                preferred_khz=preferred_khz,
            )
            if cursor == self._cursor:
                return False
            self._cursor = cursor
            self._generation += 1
            return True

    def append(self, frame: WaterfallFrame, *, draw: bool = True) -> None:
        now = self.clock()
        should_draw = False
        with self._lock:
            if frame.flags_x_zoom_server is not None:
                self.zoom = min(frame.flags_x_zoom_server & WF_ZOOM_MASK, self.zoom_max)
            if frame.start_khz is not None and frame.span_khz is not None:
                start_khz = frame.start_khz
                end_khz = frame.start_khz + frame.span_khz
                self._frequency_range = (start_khz, end_khz)
                if self.show_cursor and frame.bin_width_hz is not None:
                    if self._cursor is None:
                        preferred_khz = self.initial_cursor_khz
                        if preferred_khz is None:
                            preferred_khz = self.tuned_khz
                        main_step_hz, _small_step_hz = self.step_pairs_hz[self.step_pair_index]
                        self._cursor = WaterfallCursor.for_span(
                            start_khz=start_khz,
                            end_khz=end_khz,
                            bin_width_hz=frame.bin_width_hz,
                            step_hz=main_step_hz,
                            preferred_khz=preferred_khz,
                        )
                    else:
                        self._cursor = self._cursor.with_span(
                            start_khz=start_khz,
                            end_khz=end_khz,
                            bin_width_hz=frame.bin_width_hz,
                        )
            self.history.append(frame)
            self._generation += 1
            if draw and (self._last_draw is None or now - self._last_draw >= self.refresh_interval):
                self._last_draw = now
                should_draw = True
        if should_draw:
            self.draw()

    def _render_snapshot(
        self,
    ) -> tuple[RasterImage, tuple[float, float] | None, str | None, int]:
        with self._lock:
            rows = self.history.rows(newest_at_top=self.newest_at_top, pad_dbm=-255)
            frequency_range = self._frequency_range
            cursor = self._cursor
            cursor_khz = None if cursor is None else cursor.frequency_khz
            main_step_hz, small_step_hz = self.step_pairs_hz[self.step_pair_index]
            status = self._format_cursor_status(
                cursor,
                self.tuned_khz,
                mode=self.mode,
                main_step_hz=main_step_hz,
                small_step_hz=small_step_hz,
                keyboard_enabled=self.keyboard_enabled,
            )
            generation = self._generation
        if not rows:
            raise ValueError("cannot render an empty waterfall history")
        image = render_dbm_rows(rows, min_dbm=self.min_dbm, max_dbm=self.max_dbm)
        if frequency_range is not None and (self.tuned_khz is not None or cursor_khz is not None):
            start_khz, end_khz = frequency_range
            image = apply_frequency_overlay(
                image,
                WaterfallOverlay(
                    start_khz=start_khz,
                    end_khz=end_khz,
                    tuned_khz=self.tuned_khz,
                    low_cut_hz=self.low_cut_hz if self.show_passband else None,
                    high_cut_hz=self.high_cut_hz if self.show_passband else None,
                    show_tuned_marker=self.show_tuned_marker,
                    cursor_khz=cursor_khz,
                ),
            )
        return image, frequency_range, status, generation

    def raster(self) -> RasterImage:
        image, _frequency_range, _status, _generation = self._render_snapshot()
        return image

    def draw(self) -> None:
        image, frequency_range, status, generation = self._render_snapshot()
        if frequency_range is not None:
            set_frequency_range = getattr(self.backend, "set_frequency_range", None)
            if set_frequency_range is not None:
                set_frequency_range(*frequency_range)
        if status is not None:
            set_status_line = getattr(self.backend, "set_status_line", None)
            if set_status_line is not None:
                set_status_line(status)
        self.backend.draw(image)
        with self._lock:
            self._drawn_generation = max(self._drawn_generation, generation)

    def finish(self) -> None:
        if self.needs_draw:
            self.draw()
        finish_backend = getattr(self.backend, "finish", None)
        if finish_backend is not None:
            finish_backend()


def preview_terminal_fixture(path: Path, viewer: WaterfallTerminalViewer) -> int:
    """Load all W/F frames and metadata from a fixture and draw one final raster."""
    frames = 0
    state = WaterfallReceiverState()
    for event in load_jsonl_events(path):
        if event.dir != "rx" or event.stream != "wf":
            continue
        if event.type == "msg":
            state = state.apply_msg_params(parse_msg(event.raw["text"]).params)
        elif event.type == "binary":
            frame = contextualize_waterfall_frame(
                parse_waterfall_uncompressed(event.binary_payload),
                state,
            )
            viewer.append(frame, draw=False)
            frames += 1
    if frames:
        viewer.finish()
    return frames


async def control_waterfall_cursor(
    viewer: WaterfallTerminalViewer,
    *,
    redraw_requested: asyncio.Event,
    stop_event: Event,
    input_fd: int,
    command_queue: queue.Queue[str] | None = None,
) -> None:
    """Read local cursor controls in cbreak mode and always restore terminal input."""
    loop = asyncio.get_running_loop()
    queue: asyncio.Queue[bytes] = asyncio.Queue()
    decoder = CursorKeyDecoder()
    previous_attributes = termios.tcgetattr(input_fd)

    def read_ready() -> None:
        try:
            data = os.read(input_fd, 64)
        except BlockingIOError:
            return
        if data:
            queue.put_nowait(data)
        else:
            stop_event.set()
            queue.put_nowait(b"q")

    try:
        tty.setcbreak(input_fd, termios.TCSANOW)
        loop.add_reader(input_fd, read_ready)
        while not stop_event.is_set():
            for action in decoder.feed(await queue.get()):
                if action.kind == "move":
                    if viewer.move_cursor_steps(action.bins):
                        redraw_requested.set()
                elif action.kind == "move-small":
                    if viewer.move_cursor_steps(action.bins, small=True):
                        redraw_requested.set()
                elif action.kind == "cycle-step":
                    if viewer.cycle_step_pair(action.bins):
                        redraw_requested.set()
                elif action.kind == "reset":
                    if viewer.reset_cursor():
                        redraw_requested.set()
                elif action.kind == "recenter" and command_queue is not None:
                    command = viewer.recenter_command()
                    if command is not None:
                        command_queue.put(command)
                elif action.kind == "zoom" and command_queue is not None:
                    command = viewer.zoom_command(action.bins)
                    if command is not None:
                        command_queue.put(command)
                elif action.kind == "quit":
                    stop_event.set()
                    return
    finally:
        loop.remove_reader(input_fd)
        termios.tcsetattr(input_fd, termios.TCSANOW, previous_attributes)


async def view_live_waterfall(
    config: LiveWaterfallCaptureConfig,
    viewer: WaterfallTerminalViewer,
    *,
    allow_live: bool = False,
    websocket_connect: Callable[..., Any] | None = None,
    keyboard_fd: int | None = None,
) -> Path:
    """Receive frames promptly while a bounded background renderer draws the latest state."""
    redraw_requested = asyncio.Event()
    stop_event = Event()
    command_queue: queue.Queue[str] = queue.Queue()
    stopping = False

    def receive_frame(frame: WaterfallFrame) -> None:
        viewer.append(frame, draw=False)
        redraw_requested.set()

    async def render_latest() -> None:
        next_draw = asyncio.get_running_loop().time() + viewer.refresh_interval
        while True:
            await redraw_requested.wait()
            redraw_requested.clear()
            if not viewer.needs_draw:
                if stopping:
                    return
                continue
            delay = next_draw - asyncio.get_running_loop().time()
            if delay > 0:
                await asyncio.sleep(delay)
            await asyncio.to_thread(viewer.draw)
            next_draw = asyncio.get_running_loop().time() + viewer.refresh_interval
            if viewer.needs_draw:
                redraw_requested.set()
            elif stopping:
                return

    capture_task = asyncio.create_task(
        capture_live_waterfall(
            config,
            allow_live=allow_live,
            stop_event=stop_event,
            frame_callback=receive_frame,
            command_queue=command_queue,
            websocket_connect=websocket_connect,
        )
    )
    render_task = asyncio.create_task(render_latest())
    keyboard_task = (
        asyncio.create_task(
            control_waterfall_cursor(
                viewer,
                redraw_requested=redraw_requested,
                stop_event=stop_event,
                input_fd=keyboard_fd,
                command_queue=command_queue,
            )
        )
        if keyboard_fd is not None
        else None
    )
    try:
        done, _pending = await asyncio.wait(
            (capture_task, render_task),
            return_when=asyncio.FIRST_COMPLETED,
        )
        if render_task in done:
            render_task.result()
            raise RuntimeError("waterfall renderer stopped unexpectedly")
        return capture_task.result()
    finally:
        stopping = True
        stop_event.set()
        redraw_requested.set()
        if not capture_task.done():
            capture_task.cancel()
            await asyncio.gather(capture_task, return_exceptions=True)
        if keyboard_task is not None:
            keyboard_task.cancel()
            await asyncio.gather(keyboard_task, return_exceptions=True)
        try:
            await render_task
        finally:
            await asyncio.to_thread(viewer.finish)


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Raster KiwiSDR waterfall viewer for Kitty-capable terminals")
    parser.add_argument("--config", type=Path, help="TOML config path; otherwise use normal config discovery")
    parser.add_argument("--fixture", type=Path, help="render a W/F JSONL fixture without network access")
    parser.add_argument("--backend", choices=("kitty",), default="kitty")
    parser.add_argument("--rows", type=int, help="waterfall history height in source image pixels")
    parser.add_argument("--terminal-columns", type=int, help="Kitty placement width in terminal cells")
    parser.add_argument("--terminal-rows", type=int, help="Kitty placement height in terminal cells; 0 uses auto size")
    parser.add_argument("--newest-at-top", action=argparse.BooleanOptionalAction, default=None)
    parser.add_argument("--render-min-db", type=float)
    parser.add_argument("--render-max-db", type=float)
    parser.add_argument("--refresh-hz", type=float)
    parser.add_argument("--label-columns-per-tick", type=int, help="target terminal columns per frequency label")
    parser.add_argument("--tuned-khz", type=float, help="tuned-frequency marker; live default is --center-khz")
    parser.add_argument("--low-cut-hz", type=int, help="passband low edge relative to tuned frequency")
    parser.add_argument("--high-cut-hz", type=int, help="passband high edge relative to tuned frequency")
    parser.add_argument("--show-tuned-marker", action=argparse.BooleanOptionalAction, default=None)
    parser.add_argument("--show-passband", action=argparse.BooleanOptionalAction, default=None)
    parser.add_argument("--show-cursor", action=argparse.BooleanOptionalAction, default=None)
    parser.add_argument("--cursor-khz", type=float, help="initial exact local cursor frequency")
    parser.add_argument("--mode", help="mode whose configured main/small cursor step pairs are used")
    parser.add_argument("--step-pair", type=int, help="initial zero-based configured mode step-pair index")
    parser.add_argument("--keyboard", action=argparse.BooleanOptionalAction, default=None)
    parser.add_argument("--force", action="store_true", help="emit Kitty graphics even when capability detection fails")
    parser.add_argument("--host", default="10.0.0.40")
    parser.add_argument("--port", type=int, default=8073)
    parser.add_argument("--center-khz", type=float)
    parser.add_argument("--zoom", type=int)
    parser.add_argument("--max-db", type=int, default=0, help="receiver waterfall max dB setting")
    parser.add_argument("--min-db", type=int, default=-110, help="receiver waterfall min dB setting")
    parser.add_argument("--speed", type=int)
    parser.add_argument(
        "--interp",
        type=int,
        default=None,
        help="FFT-bin reduction: 0..4=max/min/last/drop/CMA; 10..14=same with CIC compensation",
    )
    parser.add_argument("--duration-seconds", type=float, help="0 means unlimited; defaults to [live]")
    parser.add_argument("--max-frames", type=int, help="0 means unlimited; defaults to [live]")
    parser.add_argument("--timestamp", type=int)
    parser.add_argument("--save-fixture", type=Path)
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--allow-live", action="store_true")
    return parser


def apply_waterfall_config(args: argparse.Namespace, config: KiwiClientConfig) -> argparse.Namespace:
    """Apply `[waterfall]` defaults only where the CLI left a value unset."""
    waterfall = config.waterfall
    defaults = {
        "center_khz": waterfall.center_khz,
        "zoom": waterfall.zoom,
        "rows": waterfall.history_rows,
        "terminal_rows": None if waterfall.terminal_rows == 0 else waterfall.terminal_rows,
        "render_min_db": waterfall.render_min_db,
        "render_max_db": waterfall.render_max_db,
        "speed": waterfall.speed,
        "refresh_hz": waterfall.refresh_hz,
        "interp": waterfall.interp,
        "label_columns_per_tick": waterfall.label_columns_per_tick,
        "show_tuned_marker": waterfall.show_tuned_marker,
        "show_passband": waterfall.show_passband,
        "show_cursor": waterfall.show_cursor,
        "keyboard": waterfall.keyboard,
        "mode": str(config.default_state.get("mode", "am")),
        "step_pair": waterfall.cursor_step_pair,
        "tuned_khz": waterfall.tuned_khz,
        "low_cut_hz": waterfall.low_cut_hz,
        "high_cut_hz": waterfall.high_cut_hz,
        "duration_seconds": config.live.duration_seconds,
        "max_frames": config.live.max_frames,
        "newest_at_top": False,
    }
    for name, value in defaults.items():
        if getattr(args, name) is None:
            setattr(args, name, value)
    mode = args.mode.lower()
    if mode not in config.tuning.mode_step_pairs:
        raise ValueError(f"no configured cursor step pairs for mode: {mode}")
    args.mode = mode
    args.cursor_step_pairs = config.tuning.mode_step_pairs[mode]
    args.receivers_restricted = config.receivers.restricted
    args.allowed_receivers = config.receivers.allowed
    return args


def _capture_config(args: argparse.Namespace, output: Path) -> LiveWaterfallCaptureConfig:
    return LiveWaterfallCaptureConfig(
        host=args.host,
        port=args.port,
        output=output,
        center_khz=args.center_khz,
        zoom=args.zoom,
        maxdb=args.max_db,
        mindb=args.min_db,
        speed=args.speed,
        interp=args.interp,
        duration_seconds=args.duration_seconds,
        max_frames=args.max_frames,
        timestamp=args.timestamp,
        overwrite=args.overwrite,
        receivers_restricted=args.receivers_restricted,
        allowed_receivers=args.allowed_receivers,
    )


def _viewer(args: argparse.Namespace, output: BinaryIO) -> WaterfallTerminalViewer:
    terminal_size = shutil.get_terminal_size(fallback=(120, 40))
    default_columns, default_rows = default_terminal_placement(
        columns=terminal_size.columns,
        lines=terminal_size.lines,
    )
    backend = KittyTerminalBackend(
        output=output,
        columns=args.terminal_columns if args.terminal_columns is not None else default_columns,
        rows=args.terminal_rows if args.terminal_rows is not None else default_rows,
        label_columns_per_tick=args.label_columns_per_tick,
        force=args.force,
    )
    tuned_khz = args.tuned_khz
    if tuned_khz is None and args.fixture is None:
        tuned_khz = args.center_khz
    return WaterfallTerminalViewer(
        backend=backend,
        max_rows=args.rows,
        min_dbm=args.render_min_db,
        max_dbm=args.render_max_db,
        newest_at_top=args.newest_at_top,
        refresh_hz=args.refresh_hz,
        tuned_khz=tuned_khz,
        low_cut_hz=args.low_cut_hz,
        high_cut_hz=args.high_cut_hz,
        show_tuned_marker=args.show_tuned_marker,
        show_passband=args.show_passband,
        show_cursor=args.show_cursor,
        cursor_khz=args.cursor_khz,
        mode=args.mode,
        step_pairs_hz=args.cursor_step_pairs,
        step_pair_index=args.step_pair,
        zoom=args.zoom,
        keyboard_enabled=args.keyboard and args.fixture is None,
    )


def main(argv: list[str] | None = None) -> int:
    parser = build_arg_parser()
    args = parser.parse_args(argv)
    config_path = discover_config_path(args.config)
    app_config = load_config(config_path) if config_path is not None else load_config()
    args = apply_waterfall_config(args, app_config)
    if args.fixture is not None and (args.dry_run or args.allow_live or args.save_fixture is not None):
        parser.error("--fixture cannot be combined with live or dry-run options")
    output = sys.stdout.buffer
    try:
        viewer = _viewer(args, output)
        if args.fixture is not None:
            if preview_terminal_fixture(args.fixture, viewer) == 0:
                raise ValueError(f"fixture contains no W/F frames: {args.fixture}")
            return 0

        capture_output = args.save_fixture or Path("<temporary-wf-terminal.jsonl>")
        capture_config = _capture_config(args, capture_output)
        if args.dry_run:
            capture_config.validate()
            plan = capture_config.dry_run_plan()
            plan.update(
                {
                    "backend": args.backend,
                    "history_rows": args.rows,
                    "render_min_db": args.render_min_db,
                    "render_max_db": args.render_max_db,
                    "refresh_hz": args.refresh_hz,
                    "label_columns_per_tick": args.label_columns_per_tick,
                    "tuned_khz": viewer.tuned_khz,
                    "low_cut_hz": viewer.low_cut_hz if viewer.show_passband else None,
                    "high_cut_hz": viewer.high_cut_hz if viewer.show_passband else None,
                    "show_tuned_marker": viewer.show_tuned_marker,
                    "show_passband": viewer.show_passband,
                    "show_cursor": viewer.show_cursor,
                    "cursor_mode": viewer.mode,
                    "cursor_step_pair": viewer.step_pair_index,
                    "cursor_step_pairs_hz": viewer.step_pairs_hz,
                    "keyboard": args.keyboard,
                    "receivers_restricted": app_config.receivers.restricted,
                    "allowed_receivers": app_config.receivers.allowed,
                    "config": str(config_path) if config_path is not None else None,
                }
            )
            print(json.dumps(plan, indent=2, sort_keys=True))
            return 0
        if not args.allow_live:
            raise LiveCaptureError("live terminal waterfall requires --allow-live; use --fixture or --dry-run without network")
        keyboard_fd = sys.stdin.fileno() if args.keyboard and sys.stdin.isatty() else None
        if args.save_fixture is not None:
            asyncio.run(
                view_live_waterfall(
                    capture_config,
                    viewer,
                    allow_live=True,
                    keyboard_fd=keyboard_fd,
                )
            )
        else:
            with tempfile.TemporaryDirectory(prefix="kiwi-wf-terminal-") as directory:
                temp_config = _capture_config(args, Path(directory) / "waterfall.jsonl")
                asyncio.run(
                    view_live_waterfall(
                        temp_config,
                        viewer,
                        allow_live=True,
                        keyboard_fd=keyboard_fd,
                    )
                )
        return 0
    except (LiveCaptureError, OSError, RuntimeError, ValueError) as exc:
        parser.error(str(exc))
    return 2


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
