"""Fixture-first integrated curses and Kitty waterfall shell."""

from __future__ import annotations

import argparse
import curses
import json
import math
import os
import sqlite3
import sys
import time
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any, BinaryIO, Mapping

from kiwi_client.gui_app import FixtureWaterfallTimeline, WaterfallGuiModel
from kiwi_client.ndb_logbook import Logbook, reception_draft, utc_time
from kiwi_client.reception_ui import ReceptionIndex, logging_panel_rows, reception_panel_lines, station_spreadsheet
from kiwi_client.console_panels import main_panel_rows
from kiwi_client.console_state import ConsoleSettingsCheckpoint, startup_waterfall_zoom, startup_waterfall_scale, normalize_console_cw_bandwidth
from kiwi_client.rna_console import CallsignSearchPage, RnaBrowser, add_rna_arguments, browser_from_args
from kiwi_client.state_store import load_presets_file
from kiwi_client.station_memory import passband_center_khz, catalogue_reference_khz
from kiwi_client.tui import InputMode, TuiInputState, handle_tui_key, render_tui_hints
from kiwi_client.waterfall_levels import WaterfallLevelController
from kiwi_client.waterfall_raster import RasterImage, encode_png
from kiwi_client.waterfall_scale import compose_waterfall_scale, ScalePaneTooSmall
from kiwi_client.terminal_geometry import terminal_cell_pixels
from kiwi_client.waterfall_terminal import (
    choose_frequency_tick_step,
    encode_kitty_image,
    frequency_ticks,
    terminal_supports_kitty,
)


@dataclass(frozen=True)
class IntegratedTerminalLayout:
    """Terminal-cell regions for the integrated waterfall and text UI."""

    columns: int
    lines: int
    waterfall_top: int
    waterfall_rows: int
    divider_row: int
    tui_top: int
    tui_rows: int

    @classmethod
    def compute(cls, *, columns: int, lines: int) -> "IntegratedTerminalLayout":
        if columns < 40 or lines < 12:
            raise ValueError("integrated terminal requires at least 40 columns and 12 lines")
        waterfall_rows = lines // 2
        divider_row = waterfall_rows
        tui_top = divider_row + 1
        return cls(
            columns=columns,
            lines=lines,
            waterfall_top=0,
            waterfall_rows=waterfall_rows,
            divider_row=divider_row,
            tui_top=tui_top,
            tui_rows=lines - tui_top,
        )


def format_frequency_tick_ruler(
    start_khz: float,
    end_khz: float,
    *,
    columns: int,
) -> tuple[str, str]:
    """Return exact tick marks plus unit-free, non-overlapping frequency labels."""
    ticks = frequency_ticks(start_khz, end_khz, columns=columns, include_units=False)
    target_labels = max(2, columns // 18)
    major_step = choose_frequency_tick_step((end_khz - start_khz) / (target_labels - 1))
    ticks = tuple(
        tick
        for tick in ticks
        if not tick.edge
        or abs(tick.frequency_khz / major_step - round(tick.frequency_khz / major_step)) < 1e-9
    )
    marks = [" "] * columns
    labels = [" "] * columns
    span = end_khz - start_khz
    for tick in ticks:
        position = round((tick.frequency_khz - start_khz) / span * (columns - 1))
        marks[position] = "|"
        labels[tick.label_start:tick.label_stop] = tick.label
    return "".join(marks), "".join(labels)


def format_preset_ruler(
    presets: Mapping[str, Mapping[str, Any]],
    start_khz: float,
    end_khz: float,
    *,
    columns: int,
) -> str:
    """Place visible preset register/frequency labels without overlap."""
    if columns <= 0:
        raise ValueError("preset ruler columns must be positive")
    if end_khz <= start_khz:
        raise ValueError("preset ruler end must be greater than start")
    ruler = [" "] * columns
    occupied: list[tuple[int, int]] = []
    span = end_khz - start_khz
    candidates: list[tuple[float, str]] = []
    for register, preset in presets.items():
        frequency = preset.get("frequency_khz")
        if frequency is None:
            continue
        frequency_khz = float(frequency)
        if start_khz <= frequency_khz <= end_khz:
            candidates.append((frequency_khz, f"{register} {frequency_khz:.3f}"))
    for frequency_khz, label in sorted(candidates):
        label = label[:max(0, columns - 1)]
        marker = round((frequency_khz - start_khz) / span * (columns - 1))
        start = marker + 1 if marker + 1 + len(label) <= columns else marker - len(label)
        start = max(0, start)
        stop = start + len(label)
        used_start = min(marker, start)
        used_stop = max(marker + 1, stop)
        if any(used_start < previous_stop + 1 and used_stop + 1 > previous_start for previous_start, previous_stop in occupied):
            continue
        ruler[marker] = "|"
        ruler[start:stop] = label
        occupied.append((used_start, used_stop))
    return "".join(ruler)


def rssi_s_unit(rssi_db: float) -> str:
    """Convert HF RSSI to a conventional S-unit label (S9 = -73 dBm)."""
    if rssi_db > -73:
        return f"S9+{round(rssi_db + 73)}"
    unit = round(9 + (rssi_db + 73) / 6)
    return f"S{min(9, max(1, unit))}"


def format_rssi_indicator(rssi_db: float | None, *, width: int = 18) -> str:
    """Format one bounded text signal-strength meter for the curses panel."""
    if width <= 0:
        raise ValueError("RSSI indicator width must be positive")
    if rssi_db is None:
        return f"RSSI ------ dBm ----- [{'-' * width}]"
    fraction = min(1.0, max(0.0, (rssi_db + 130.0) / 110.0))
    filled = round(fraction * width)
    bar = "#" * filled + "-" * (width - filled)
    return f"RSSI {rssi_db:6.1f} dBm {rssi_s_unit(rssi_db):<5} [{bar}]"


def nearest_step_pair_index(
    pairs: tuple[tuple[float, float], ...],
    *,
    main_hz: float,
    small_hz: float,
) -> int:
    """Choose the configured pair nearest requested console main/fine steps."""
    if not pairs or main_hz <= 0 or small_hz <= 0:
        raise ValueError("step pairs and requested steps must be positive")
    return min(
        range(len(pairs)),
        key=lambda index: abs(pairs[index][0] - main_hz) + abs(pairs[index][1] - small_hz),
    )


class ControllerConsoleSource:
    """Bind the console display to one controller-owned paired live session."""

    def __init__(self, controller, *, model: WaterfallGuiModel, audio: bool = False) -> None:
        self.controller = controller
        self.model = model
        self.audio = audio
        self.started = False
        self._last_generation = 0

    def start(self) -> None:
        if self.started:
            return
        command = "radio-bg --allow-live" + ("" if self.audio else " --null-sink")
        self.controller.execute(command)
        self.model.bind_publisher(self.controller.waterfall_snapshots, preserve_session_view=True)
        self.model.session = self.controller.paired_session
        self.model.action_dispatch = self.controller.dispatch_session_action
        self.model._session_mapped = True
        self.started = True

    def poll_generation(self) -> int:
        sync_status = getattr(self.controller, "paired_session_status", None)
        if sync_status is not None:
            sync_status()
        if self.model.publisher is not self.controller.waterfall_snapshots:
            self.model.bind_publisher(self.controller.waterfall_snapshots, preserve_session_view=True)
            self._last_generation = 0
            return -1
        snapshot = self.model.publisher.latest()
        generation = 0 if snapshot is None else snapshot.generation
        changed = generation != self._last_generation
        self._last_generation = generation
        return generation if changed else 0

    def stop(self) -> None:
        if not self.started:
            return
        self.started = False
        self.controller.execute("stop")
        self.controller.execute("wait 5")


class KittyPanePresenter:
    """Place one replaceable Kitty image at an absolute curses-owned region."""

    def __init__(
        self,
        *,
        output: BinaryIO,
        image_id: int = 41,
        placement_id: int = 41,
        force: bool = False,
        environ: Mapping[str, str] | None = None,
    ) -> None:
        self.output = output
        self.image_ids = (image_id, image_id + 1)
        self.placement_ids = (placement_id, placement_id + 1)
        self.force = force
        self.environ = os.environ if environ is None else environ
        self._last_key: tuple[int, ...] | None = None
        self._active_slot: int | None = None
        self._finished = False

    def draw(
        self,
        image: RasterImage,
        layout: IntegratedTerminalLayout,
        *,
        generation: int | None = None,
    ) -> bool:
        if not self.force and not terminal_supports_kitty(self.environ):
            raise RuntimeError("terminal does not advertise Kitty graphics support")
        key = None if generation is None else (generation, layout.columns, layout.waterfall_rows, image.width, image.height)
        if key is not None and key == self._last_key:
            return False
        slot = 0 if self._active_slot is None else 1 - self._active_slot
        image_id = self.image_ids[slot]
        placement_id = self.placement_ids[slot]
        payload = encode_kitty_image(
            encode_png(image),
            image_id=image_id,
            placement_id=placement_id,
            columns=layout.columns,
            rows=layout.waterfall_rows,
        )
        position = f"\x1b[{layout.waterfall_top + 1};1H".encode("ascii")
        previous_slot = self._active_slot
        self.output.write(b"\x1b7" + position + payload + b"\x1b8")
        if previous_slot is not None:
            previous_id = self.image_ids[previous_slot]
            self.output.write(f"\x1b_Ga=d,d=i,i={previous_id},q=2;\x1b\\".encode("ascii"))
        flush = getattr(self.output, "flush", None)
        if flush is not None:
            flush()
        self._last_key = key
        self._active_slot = slot
        return True

    @property
    def active_image_id(self) -> int | None:
        return None if self._active_slot is None else self.image_ids[self._active_slot]

    def invalidate(self) -> None:
        self._last_key = None

    def clear(self) -> bool:
        """Delete the current placement without finishing the reusable presenter."""
        if self._active_slot is None:
            return False
        image_id = self.image_ids[self._active_slot]
        self.output.write(f"\x1b_Ga=d,d=i,i={image_id},q=2;\x1b\\".encode("ascii"))
        flush = getattr(self.output, "flush", None)
        if flush is not None:
            flush()
        self._active_slot = None
        self._last_key = None
        return True

    def finish(self) -> None:
        if self._finished:
            return
        self.clear()
        self._finished = True


def set_console_frequency(model: WaterfallGuiModel, frequency_khz: float):
    """Tune directly and recenter when the entered frequency is outside the viewport."""
    tuned = model.set_tuned_frequency(frequency_khz)
    recentered = None
    try:
        start_khz, end_khz = model.display_frequency_range()
    except ValueError:
        return tuned, recentered
    if frequency_khz < start_khz or frequency_khz > end_khz:
        recentered = model.recenter()
    return tuned, recentered


def tune_console_one_screen(model: WaterfallGuiModel, direction: int):
    """Tune and recenter one current visible span lower or higher."""
    if direction not in (-1, 1):
        raise ValueError("screen direction must be -1 or 1")
    start_khz, end_khz = model.display_frequency_range()
    frequency_khz = model.session.state.frequency_khz + direction * (end_khz - start_khz)
    tuned = model.set_tuned_frequency(frequency_khz)
    return tuned, model.recenter()


def tune_console_selection(model: WaterfallGuiModel, delta: int, *, small: bool = False):
    """Move and immediately tune; recenter only after crossing the visible edge."""
    model.move_selection(delta, small=small, clamp_to_view=False)
    return set_console_frequency(model, model.session.state.selected_khz)


CW_BANDWIDTHS_HZ = (10, 20, 30, 50, 100, 500)


def step_console_cw_bandwidth(model: WaterfallGuiModel, direction: int, controller=None) -> str:
    """Request a CW width centered on the same RF frequency, including odd widths."""
    if direction not in (-1, 1):
        raise ValueError("bandwidth direction must be -1 or 1")
    state = model.session.state
    if state.mode != "cw":
        return "j/k bandwidth steps are available in CW mode only"
    width = state.high_cut_hz - state.low_cut_hz
    choices = ([CW_BANDWIDTHS_HZ[0]] if width < CW_BANDWIDTHS_HZ[0] else
               [value for value in CW_BANDWIDTHS_HZ if (value - width) * direction > 0])
    if not choices:
        return f"CW bandwidth {width:g} Hz; {'minimum' if direction < 0 else 'maximum'} step reached"
    midpoint = (state.low_cut_hz + state.high_cut_hz) / 2
    ordered = sorted(choices, reverse=direction < 0)
    for new_width in ordered:
        # Canonical parity avoids cumulative half-Hz drift when toggling 2/5/10.
        low = math.floor(midpoint) - new_width // 2
        high = low + new_width
        shift_hz = midpoint - (low + high) / 2
        if shift_hz == 0 or state.frequency_decimals >= 4:
            break
    else:
        return 'No centered step available; 0.5 Hz compensation needs command_frequency_decimals >= 4'
    frequency = state.frequency_khz + shift_hz / 1000
    if controller is not None:
        command = f"filter {low} {high}"
        if shift_hz:
            command += f"; tune {frequency:.9f}"
        controller.execute(command)  # Atomic batch: one final modulation command.
    else:
        model.session.state = replace(state, low_cut_hz=low, high_cut_hz=high,
                                      frequency_khz=frequency, selected_khz=state.selected_khz + shift_hz / 1000)
    skipped = '' if new_width == ordered[0] else '; skipped half-Hz step: increase command_frequency_decimals to 4+'
    return (f"CW bandwidth {new_width} Hz requested | passband {low}..{high} Hz | "
            f"RF center {passband_center_khz(model.session.state):.6f} kHz{skipped}")


def discard_console_mouse_event(key):
    """Consume reported mouse input so wheel motion cannot masquerade as arrow keys."""
    if key != curses.KEY_MOUSE:
        return key
    try:
        curses.getmouse()
    except curses.error:
        pass
    return None


def _safe_line(screen, row: int, text: str, columns: int, attributes: int = 0) -> None:
    try:
        screen.addnstr(row, 0, text.ljust(columns), max(0, columns - 1), attributes)
    except curses.error:
        pass


def _apply_preset(model: WaterfallGuiModel, preset: Mapping[str, Any]) -> None:
    model.set_tuned_frequency(float(preset["frequency_khz"]))
    state = model.session.state
    changes: dict[str, Any] = {}
    for name in ("mode", "low_cut_hz", "high_cut_hz"):
        if name in preset:
            changes[name] = preset[name]
    if changes:
        model.session.state = replace(state, **changes)


def tune_rna_component(browser: RnaBrowser, model: WaterfallGuiModel, controller=None) -> str:
    """Pass the RF component to normal tuning; never pre-apply the CW offset."""
    component = browser.component
    if component is None:
        raise ValueError("no RNA station selected")
    if controller is not None:
        controller.execute("mode cw")
    elif model.session.state.mode != "cw":
        model.session.state = replace(model.session.state, mode="cw", low_cut_hz=600, high_cut_hz=1000)
    frequency_khz = catalogue_reference_khz(model.session.state, component.frequency_khz)
    if component.kind == "stored":
        frequency_khz = component.frequency_khz
        stored = browser.memory.records[browser.selected.station.key]['stored']
        state = model.session.state
        midpoint = (state.low_cut_hz + state.high_cut_hz) / 2
        recalled_width = max(CW_BANDWIDTHS_HZ[0], int(stored['bandwidth_hz']))
        low = round(midpoint - recalled_width / 2)
        high = low + recalled_width
        if controller is not None:
            controller.execute(f"filter {low} {high}")
        else:
            model.session.state = replace(state, low_cut_hz=low, high_cut_hz=high)
        # A stored frequency means actual RF passband center, not the CW UI reference.
        frequency_khz -= (model.session.state.cw_offset_hz + (low + high) / 2) / 1000
    set_console_frequency(model, frequency_khz)
    return f"RNA {browser.selected.station.ident} {component.kind} {component.frequency_khz:.3f} kHz; ID not confirmed"


def execute_console_rna_command(browser: RnaBrowser, command: str, model: WaterfallGuiModel) -> str:
    if command.strip() == "rna store":
        return browser.store_tuning(model.session.state)
    if command.strip() == "rna forget":
        return browser.forget_tuning()
    return browser.command(command, model.session.state.frequency_khz)


def run_fixture_shell(
    screen,
    *,
    model: WaterfallGuiModel,
    timeline: FixtureWaterfallTimeline | None,
    live_source: ControllerConsoleSource | None,
    presets: Mapping[str, Mapping[str, Any]],
    presenter: KittyPanePresenter,
    levels: WaterfallLevelController,
    tui_controller,
    tui_config,
    source_fps: float,
    refresh_hz: float,
    scale_font_backend: str = "auto",
    scale_font_name: str = "DejaVuSansMono.ttf",
    show_cw_offset_marker: bool = False,
    settings_checkpoint: ConsoleSettingsCheckpoint | None = None,
    demo_seconds: float | None = None,
    rna_browser: RnaBrowser | None = None,
    logbook_path: Path | None = None,
    log_event: str | None = None,
) -> None:
    """Run fixture publication, curses text, and Kitty presentation in one thread."""
    screen.nodelay(True)
    screen.keypad(True)
    mouse_reporting = False
    try:
        curses.mousemask(curses.ALL_MOUSE_EVENTS)
        mouse_reporting = True
    except curses.error:
        pass
    try:
        curses.curs_set(0)
    except curses.error:
        pass
    if curses.has_colors():
        curses.start_color()
        curses.use_default_colors()
    if (timeline is None) == (live_source is None):
        raise ValueError("console requires exactly one fixture or live source")
    if timeline is not None:
        timeline.advance(model.publisher)
    started = time.monotonic()
    next_source = started
    next_refresh = 0.0
    dirty = True
    full_redraw = True
    entry: str | None = None
    search_entry: str | None = None
    search_page: CallsignSearchPage | None = None
    catalogue_command: str | None = None
    log_draft: dict | None = None
    log_original: dict | None = None
    log_delete_pending = False
    reception_index = ReceptionIndex(logbook_path)
    next_history_refresh = 0.0
    log_entry: str | None = None
    pending_preset = False
    tui_input = TuiInputState() if tui_controller is not None and tui_config is not None else None
    last_response = None
    message = "live paired session starting" if live_source is not None else "fixture-only; no receiver connection"
    if rna_browser is not None:
        try:
            rna_browser.save_preferences()
        except (OSError, ValueError) as exc:
            message = f"RNA state NOT saved: {exc}"

    def station_log_status(station_key):
        receiver = tui_controller.state.receiver if tui_controller is not None else "fixture"
        return reception_index.status(station_key, receiver, log_event, "live" if live_source is not None else "fixture")

    def dispatch_tui_key(key) -> None:
        nonlocal last_response, message
        if tui_input is None or tui_controller is None:
            return
        if isinstance(key, str):
            if len(key) != 1:
                return
            ch = ord(key)
        elif isinstance(key, int):
            ch = key
        else:
            return
        command = tui_input.command.strip()
        if rna_browser is not None and ch in (10, 13) and tui_input.mode == InputMode.COMMAND and (
            command == "rna" or command.startswith("rna ")
        ):
            tui_input.command = ""
            tui_input.history_index = None
            tui_input.mode = InputMode.KEYMAP
            tui_input.history.append(command)
            try:
                message = execute_console_rna_command(rna_browser, command, model)
            except (ValueError, OSError) as exc:
                message = f"error: {exc}"
            presenter.invalidate()
            return
        response, new_message = handle_tui_key(ch, tui_input, tui_controller, tui_config)
        if response is not None:
            last_response = response
        if new_message is not None:
            message = new_message
        model.main_step_hz = tui_controller.state.current_step_hz
        model.small_step_hz = tui_controller.state.current_small_step_hz

    try:
        while True:
            now = time.monotonic()
            if demo_seconds is not None and now - started >= demo_seconds:
                break
            if logbook_path is not None and now >= next_history_refresh:
                reception_index.refresh()
                next_history_refresh = now + 1.0
                dirty = True
            if timeline is not None and now >= next_source and not timeline.done:
                timeline.advance(model.publisher)
                next_source = now + 1.0 / source_fps
                dirty = True
            elif live_source is not None:
                if live_source.poll_generation() or now >= next_source:
                    next_source = now + 0.25
                    dirty = True

            if settings_checkpoint is not None:
                try:
                    settings_checkpoint.save_if_changed(tui_controller, levels=levels)
                except (OSError, ValueError) as exc:
                    message = f'Radio settings NOT saved: {exc}'
                    dirty = True
            if rna_browser is not None:
                receiver = tui_controller.state.receiver if tui_controller is not None else "fixture"
                rna_browser.set_receiver(receiver, model.session.state.frequency_khz)

            try:
                key = screen.get_wch()
            except curses.error:
                key = None
            key = discard_console_mouse_event(key)
            if key == curses.KEY_RESIZE:
                presenter.invalidate()
                full_redraw = True
                dirty = True
            elif log_draft is not None and key is not None:
                if key == "\x1b":
                    log_draft = None
                    log_entry = None
                    log_original = None
                    log_delete_pending = False
                    message = "logging cancelled; no changes saved"
                    full_redraw = True
                    presenter.invalidate()
                elif log_delete_pending:
                    if key == "D":
                        try:
                            with Logbook(logbook_path) as book:
                                book.delete(log_draft['log_id'], expected=log_original)
                            message = f"Deleted log #{log_draft['log_id']}; audit history retained"
                            log_draft = log_original = None
                            log_delete_pending = False
                            reception_index.refresh()
                            full_redraw = True
                            presenter.invalidate()
                        except (OSError, ValueError, sqlite3.Error) as exc:
                            message = f"log NOT deleted: {exc}; Esc cancels"
                elif log_entry is not None:
                    if key in ("\n", "\r"):
                        timestamp, _separator, notes = log_entry.partition("|")
                        try:
                            log_draft["heard_utc"] = utc_time(timestamp.strip()).isoformat()
                            log_draft["notes"] = notes.strip()
                            log_entry = None
                        except ValueError as exc:
                            message = str(exc)
                    elif key in ("\b", "\x7f", curses.KEY_BACKSPACE):
                        log_entry = log_entry[:-1]
                    elif isinstance(key, str) and key.isprintable():
                        log_entry += key
                elif key == "d":
                    if log_draft.get('log_id') is None:
                        message = "Unsaved reception; Esc cancels it"
                    else:
                        log_delete_pending = True
                        message = "Deletion removes this reception from logs/reports; audit history remains"
                elif key in ("y", "t", "n"):
                    try:
                        log_draft["status"] = {"y": "confirmed", "t": "tentative", "n": "not-heard"}[key]
                        with Logbook(logbook_path) as book:
                            if log_draft.get('log_id') is not None:
                                log_id = log_draft['log_id']
                                book.revise(log_id, status=log_draft['status'], heard_utc=log_draft['heard_utc'],
                                            notes=log_draft['notes'], expected=log_original)
                                message = f"Updated {log_draft['status']} log #{log_id}; original tuning evidence retained"
                            else:
                                log_id, duplicates = book.save(log_draft)
                                message = f"Saved {log_draft['status']} log #{log_id}; {duplicates} previous entries for this station/event"
                        reception_index.refresh()
                        log_draft = None
                        log_original = None
                        full_redraw = True
                        presenter.invalidate()
                    except (OSError, ValueError, sqlite3.Error) as exc:
                        message = f"log NOT saved: {exc}; retry or Esc"
                dirty = True
            elif search_entry is not None and key is not None:
                if key in ("\n", "\r"):
                    search_page = CallsignSearchPage(rna_browser, search_entry, log_status=station_log_status)
                    search_entry = None
                    message = "Search includes hidden stations; Enter accepts and tunes; Esc cancels"
                elif key == "\x1b":
                    search_entry = None
                    full_redraw = True
                    presenter.invalidate()
                elif key in ("\b", "\x7f", curses.KEY_BACKSPACE):
                    search_entry = search_entry[:-1]
                elif isinstance(key, str) and key.isprintable():
                    search_entry += key
                dirty = True
            elif search_page is not None and key is not None:
                page_size = max(1, screen.getmaxyx()[0] - 5)
                if key in ("j", curses.KEY_DOWN):
                    search_page.move(1)
                elif key in ("k", curses.KEY_UP):
                    search_page.move(-1)
                elif key == curses.KEY_NPAGE:
                    search_page.move(page_size)
                elif key == curses.KEY_PPAGE:
                    search_page.move(-page_size)
                elif key == "/":
                    search_page = None
                    search_entry = ""
                elif key in ("\n", "\r"):
                    try:
                        search_page.select()
                        message = tune_rna_component(rna_browser, model, tui_controller)
                        search_page = None
                    except (ValueError, RuntimeError, OSError) as exc:
                        message = str(exc)
                elif key in ("\x1b", ":"):
                    search_page = None
                    if key == ":":
                        if tui_input is not None:
                            dispatch_tui_key(":")
                        else:
                            catalogue_command = ""
                full_redraw = True
                presenter.invalidate()
                dirty = True
            elif catalogue_command is not None and key is not None:
                if key in ("\n", "\r"):
                    try:
                        message = execute_console_rna_command(rna_browser, catalogue_command, model)
                    except (ValueError, OSError) as exc:
                        message = f"error: {exc}"
                    catalogue_command = None
                    presenter.invalidate()
                elif key == "\x1b":
                    catalogue_command = None
                elif key in ("\b", "\x7f", curses.KEY_BACKSPACE):
                    catalogue_command = catalogue_command[:-1]
                elif isinstance(key, str) and key.isprintable():
                    catalogue_command += key
                dirty = True
            elif entry is not None and key is not None:
                if key in ("\n", "\r"):
                    try:
                        _tuned, recentered = set_console_frequency(model, float(entry))
                        suffix = "; waterfall recentered" if recentered is not None else ""
                        message = f"frequency {entry} kHz{suffix}"
                    except ValueError as exc:
                        message = str(exc)
                    entry = None
                    try:
                        curses.curs_set(0)
                    except curses.error:
                        pass
                    presenter.invalidate()
                    dirty = True
                elif key == "\x1b":
                    entry = None
                    dirty = True
                elif key in ("\b", "\x7f", curses.KEY_BACKSPACE):
                    entry = entry[:-1]
                    dirty = True
                elif isinstance(key, str) and (key.isdigit() or (key == "." and "." not in entry)):
                    entry += key
                    dirty = True
            elif tui_input is not None and (
                tui_input.mode == InputMode.COMMAND or tui_input.pending_key_action is not None
            ) and key is not None:
                dispatch_tui_key(key)
                dirty = True
                if tui_controller is not None and not tui_controller.running:
                    break
            elif pending_preset and key is not None:
                pending_preset = False
                register = str(key)
                preset = presets.get(register)
                if preset is None:
                    message = f"preset {register!r} not found"
                else:
                    _apply_preset(model, preset)
                    message = f"recalled preset {register} locally"
                    presenter.invalidate()
                dirty = True
            elif rna_browser is not None and key == "/":
                search_entry = ""
                dirty = True
            elif rna_browser is not None and tui_input is None and key == ":":
                catalogue_command = ""
                dirty = True
            elif rna_browser is not None and key in ("w", "W"):
                try:
                    if logbook_path is None:
                        raise ValueError("logging requires --logbook PATH")
                    receiver = tui_controller.state.receiver if tui_controller is not None else "fixture"
                    if rna_browser.selected is None:
                        raise ValueError("select a station first")
                    reception_index.refresh()
                    source_kind = "live" if live_source is not None else "fixture"
                    if reception_index.error:
                        raise ValueError(reception_index.error)
                    existing = (reception_index.latest(rna_browser.selected.station.key, receiver, log_event, source_kind)
                                if key == "w" else None)
                    log_delete_pending = False
                    log_original = None if existing is None else dict(existing)
                    log_draft = existing if existing is not None else reception_draft(
                        rna_browser, model.session.state, receiver=receiver, source_kind=source_kind, event=log_event)
                    log_entry = log_draft["heard_utc"] + " | " + log_draft.get('notes', '')
                    message = (f"Editing latest hearing #{log_draft['log_id']}; time/status/notes only; Esc cancels"
                               if existing is not None else "New reception: edit actual hearing time | notes; Enter then confirm")
                except ValueError as exc:
                    message = str(exc)
                dirty = True
            elif rna_browser is not None and key in (",", ".", "<", ">"):
                try:
                    message = rna_browser.cycle_nearby(passband_center_khz(model.session.state), -1 if key in (",", "<") else 1)
                    if key in ("<", ">"):
                        tune_rna_component(rna_browser, model, tui_controller)
                        message += '; tuned'
                    else:
                        message += '; shown only — tuning unchanged (y tunes shown station)'
                    rna_browser.nearby_tuned(passband_center_khz(model.session.state))
                except (ValueError, RuntimeError, OSError) as exc:
                    message = str(exc)
                presenter.invalidate()
                dirty = True
            elif rna_browser is not None and key in ("n", "N", "v", "y", "A"):
                try:
                    if key in ("n", "N"):
                        rna_browser.move(1 if key == "n" else -1)
                    elif key == "v":
                        rna_browser.cycle_component()
                    elif key == "A":
                        rna_browser.cycle_activity(model.session.state.frequency_khz)
                    if key != "A":
                        message = tune_rna_component(rna_browser, model, tui_controller)
                    else:
                        message = rna_browser.status()
                except (ValueError, RuntimeError, OSError) as exc:
                    message = str(exc)
                presenter.invalidate()
                dirty = True
            elif key in ("q", "Q"):
                if tui_input is not None:
                    dispatch_tui_key("q")
                break
            elif key == "f":
                entry = ""
                dirty = True
            elif key == "a":
                try:
                    model.toggle_audio()
                    message = f"audio {'ON' if model.session.state.audio_enabled else 'MUTED'}"
                except RuntimeError as exc:
                    message = f"audio error: {exc}"
                dirty = True
            elif key == "p" and tui_input is None:
                pending_preset = True
                message = "preset register?"
                dirty = True
            elif key in (curses.KEY_UP, curses.KEY_PPAGE):
                try:
                    tune_console_one_screen(model, 1)
                    message = "frequency up one screen"
                except ValueError as exc:
                    message = str(exc)
                presenter.invalidate()
                dirty = True
            elif key in (curses.KEY_DOWN, curses.KEY_NPAGE):
                try:
                    tune_console_one_screen(model, -1)
                    message = "frequency down one screen"
                except ValueError as exc:
                    message = str(exc)
                presenter.invalidate()
                dirty = True
            elif key in ("j", "k"):
                try:
                    message = step_console_cw_bandwidth(model, -1 if key == "j" else 1, tui_controller)
                except (ValueError, RuntimeError) as exc:
                    message = str(exc)
                presenter.invalidate()
                dirty = True
            elif key in ("h", curses.KEY_LEFT):
                tune_console_selection(model, -1, small=True)
                presenter.invalidate()
                dirty = True
            elif key in ("l", curses.KEY_RIGHT):
                tune_console_selection(model, 1, small=True)
                presenter.invalidate()
                dirty = True
            elif key in ("H", curses.KEY_SLEFT):
                tune_console_selection(model, -1)
                presenter.invalidate()
                dirty = True
            elif key in ("L", curses.KEY_SRIGHT):
                tune_console_selection(model, 1)
                presenter.invalidate()
                dirty = True
            elif key in ("\n", "\r"):
                model.tune_selected()
                presenter.invalidate()
                dirty = True
            elif key == "c":
                model.recenter()
                presenter.invalidate()
                dirty = True
            elif key in ("+", "="):
                model.zoom(1)
                presenter.invalidate()
                dirty = True
            elif key == "-":
                model.zoom(-1)
                presenter.invalidate()
                dirty = True
            elif key == "u":
                levels.set_automatic(not levels.automatic)
                dirty = True
            elif key == "[":
                levels.adjust_min(-5)
                model.set_render_scale(levels.min_dbm, levels.max_dbm)
                presenter.invalidate()
                dirty = True
            elif key == "]":
                levels.adjust_min(5)
                model.set_render_scale(levels.min_dbm, levels.max_dbm)
                presenter.invalidate()
                dirty = True
            elif key == "{":
                levels.adjust_max(-5)
                model.set_render_scale(levels.min_dbm, levels.max_dbm)
                presenter.invalidate()
                dirty = True
            elif key == "}":
                levels.adjust_max(5)
                model.set_render_scale(levels.min_dbm, levels.max_dbm)
                presenter.invalidate()
                dirty = True
            elif tui_input is not None and key is not None:
                dispatch_tui_key(key)
                dirty = True
                if tui_controller is not None and not tui_controller.running:
                    break

            if dirty and now >= next_refresh:
                lines, columns = screen.getmaxyx()
                if search_entry is not None or search_page is not None:
                    presenter.clear()
                    screen.erase()
                    page_rows = ([f"NDB callsign: /{search_entry}_", "Enter searches all catalogue IDs; Esc cancels"]
                                 if search_entry is not None else search_page.rows(lines))
                    for row, text in enumerate(page_rows[:max(0, lines - 1)]):
                        _safe_line(screen, row, text, columns)
                    _safe_line(screen, lines - 1, message, columns)
                    screen.noutrefresh()
                    curses.doupdate()
                    next_refresh = now + 1.0 / refresh_hz
                    dirty = False
                    full_redraw = True
                    time.sleep(0.005)
                    continue
                if log_draft is not None:
                    presenter.clear()
                    screen.erase()
                    if columns < 40 or lines < 12:
                        _safe_line(screen, 0, 'Logging page needs at least 40 columns / 12 rows', columns)
                        screen.refresh()
                        time.sleep(0.03)
                        continue
                    prompt = (f"DELETE #{log_draft['log_id']} {log_draft['ident']}? D confirms / Esc cancels" if log_delete_pending else
                              f"UTC | notes: {log_entry}_" if log_entry is not None else
                              f"{log_draft['ident']}: y confirmed / t tentative / n not heard / d delete / Esc cancel")
                    rows = logging_panel_rows(log_draft, prompt=prompt, message=message,
                        history=reception_index.status(log_draft['station_key'], log_draft['receiver'],
                                                       log_draft.get('event'), log_draft['source_kind']),
                        columns=columns, height=lines, entry=log_entry)
                    for row_index, text in enumerate(rows[:lines]):
                        _safe_line(screen, row_index, text, columns)
                    screen.noutrefresh()
                    curses.doupdate()
                    next_refresh = now + 1.0 / refresh_hz
                    dirty = False
                    full_redraw = True
                    time.sleep(0.005)
                    continue
                try:
                    layout = IntegratedTerminalLayout.compute(columns=columns, lines=lines)
                except ValueError as exc:
                    screen.erase()
                    _safe_line(screen, 0, str(exc), columns)
                    screen.refresh()
                    time.sleep(0.03)
                    continue
                snapshot = model.publisher.latest()
                if full_redraw:
                    screen.erase()
                else:
                    for row in range(layout.divider_row, lines):
                        try:
                            screen.move(row, 0)
                            screen.clrtoeol()
                        except curses.error:
                            pass
                state = model.session.state
                transport_status = "fixture-only"
                if live_source is not None:
                    receiver = tui_controller.state.receiver if tui_controller is not None else "unknown"
                    transport_status = f"live {receiver} | SND {state.snd_status} / W/F {state.wf_status}"
                    if state.error is not None:
                        transport_status += f" | {state.error.stream}: {state.error.message}"
                image = None
                if snapshot is None:
                    presenter.clear()
                    transport_status += " | waiting for first W/F frame"
                else:
                    if levels.observe(snapshot):
                        model.set_render_scale(levels.min_dbm, levels.max_dbm)
                        presenter.invalidate()
                    image = model.image()
                    start_khz, end_khz = model.display_frequency_range()
                    cells = terminal_cell_pixels(columns, lines)
                    try:
                        image = compose_waterfall_scale(
                            image,
                            start_khz,
                            end_khz,
                            tuned_khz=state.frequency_khz,
                            selected_khz=state.selected_khz,
                            passband_reference_khz=(
                                state.frequency_khz + state.cw_offset_hz / 1000.0
                                if state.mode == "cw"
                                else state.frequency_khz
                            ),
                            show_reference_marker=show_cw_offset_marker and state.mode == 'cw',
                            low_cut_hz=state.low_cut_hz,
                            high_cut_hz=state.high_cut_hz,
                            presets=presets,
                            annotations=() if rna_browser is None else rna_browser.annotations(start_khz, end_khz),
                            font_backend=scale_font_backend,
                            font_name=scale_font_name,
                            font_scale=max(1, round(cells.height / 10)),
                            label_target_pixels=max(20, cells.width * 15),
                            canvas_size=(columns * cells.width, layout.waterfall_rows * cells.height),
                        ).image
                    except ScalePaneTooSmall as exc:
                        image = None
                        presenter.clear()
                        transport_status += f' | {exc}'
                if catalogue_command is not None:
                    prompt = f":{catalogue_command}_"
                elif entry is not None:
                    prompt = f"frequency kHz: {entry}_"
                elif pending_preset:
                    prompt = "preset register: _"
                elif tui_input is not None and tui_input.mode == InputMode.COMMAND:
                    prompt = f":{tui_input.command}_"
                else:
                    prompt = ":"
                metrics = {}
                if tui_controller is not None:
                    metrics = tui_controller.background.status().metrics or {}
                radio_frequency_khz = (
                    state.frequency_khz + state.cw_offset_hz / 1000.0
                    if state.mode == "cw"
                    else state.frequency_khz
                )
                rssi = metrics.get('rssi_db')
                volume = tui_controller.state.volume_percent if tui_controller is not None else 0
                rssi_text = '?' if rssi is None else f'{rssi:.0f}'
                radio = (f"{state.mode.upper():3} {state.frequency_khz:10.4f} kHz  BW {state.high_cut_hz - state.low_cut_hz:4g} Hz  "
                         f"RSSI {rssi_text:>4} dBm  audio {'ON' if state.audio_enabled else 'MUTED'} {volume}%  "
                         f"step {model.small_step_hz:g}/{model.main_step_hz:g} Hz")
                station_rows = ['No RNA station selected']
                table = []
                table_title = 'STATIONS'
                receiver = tui_controller.state.receiver if tui_controller is not None else 'fixture'
                reception_rows = [f'{log_event or "general"} / {"live" if live_source else "fixture"}', receiver]
                filters = 'RNA disabled' if rna_browser is None else rna_browser.filter_summary()
                if rna_browser is not None and rna_browser.selected is not None:
                    match = rna_browser.selected
                    station = match.station
                    component = rna_browser.component
                    source_kind = 'live' if live_source is not None else 'fixture'
                    table = station_spreadsheet(rna_browser, reception_index, receiver, log_event, source_kind)
                    table_title = (f'STATIONS {rna_browser.index + 1}/{len(rna_browser.matches)} | '
                                   f'{station.ident} {component.kind.upper()} {component.frequency_khz:.6f} kHz | '
                                   f'{receiver} / {log_event or "general"} / {source_kind}')
                    station_rows = [f'{station.ident} / {station.carrier_khz:g} kHz / {rna_browser.index + 1} of {len(rna_browser.matches)}',
                        f'{component.kind.upper()} {component.frequency_khz:.6f} kHz',
                        f'{"?" if match.distance_km is None else f"{match.distance_km:.0f}"} km / '
                        f'{"?" if station.power_w is None else f"{station.power_w:g}"} W / {station.activity}',
                        f'{station.location} {station.raw_fields.get("SP", "")} {station.raw_fields.get("ITU", "")}',
                        rna_browser.details()]
                    reception_rows = reception_panel_lines(reception_index, station.key, receiver, log_event,
                                                           'live' if live_source is not None else 'fixture')
                elif rna_browser is not None:
                    station_rows = [rna_browser.status()]
                help_rows = [("/ find n/N station ,/. show nearby </> tune nearby v band " if rna_browser is not None else "") +
                             "h/l small H/L large j/k BW w edit W new q quit"]
                if rna_browser is not None:
                    help_rows.append("f freq m mode t/T steps c center +/- zoom a audio u auto : commands")
                    help_rows.append("RNA :rna store / forget / near HZ / range KM / power W / sort distance")
                # Generic TUI key hints describe different bindings; show only its
                # contextual command/prefix hints in the integrated console.
                if tui_input is not None and tui_config is not None and (
                    tui_input.mode == InputMode.COMMAND or tui_input.pending_key_action is not None
                ):
                    help_rows = (["rna store / forget; near HZ; range KM|off; power W|off; sort distance|frequency; cle on|off; site LAT LON TIMEZONE"]
                                 if tui_input.mode == InputMode.COMMAND and tui_input.command.startswith("rna")
                                 else render_tui_hints(tui_input, tui_config, tui_controller).splitlines())
                rows = main_panel_rows(columns=columns, height=layout.tui_rows + 1, radio=radio,
                    radio_title='RADIO / ' + transport_status,
                    station=station_rows, reception=reception_rows, filters=filters,
                    table=table, table_title=table_title,
                    help_rows=help_rows, message=message, prompt=prompt,
                    telemetry=f'{levels.status_text()} | RX {radio_frequency_khz:.4f} | {transport_status}')
                for offset, text in enumerate(rows[:layout.tui_rows + 1]):
                    _safe_line(screen, layout.divider_row + offset, text, columns)
                screen.noutrefresh()
                curses.doupdate()
                if image is not None and snapshot is not None:
                    presenter.draw(image, layout, generation=snapshot.generation)
                next_refresh = now + 1.0 / refresh_hz
                dirty = False
                full_redraw = False
            time.sleep(0.005)
    finally:
        if mouse_reporting:
            try:
                curses.mousemask(0)
            except curses.error:
                pass
        if live_source is not None:
            live_source.stop()
        presenter.finish()
        if settings_checkpoint is not None:
            settings_checkpoint.save_if_changed(tui_controller, levels=levels, force=True)


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Fixture-first integrated Kitty waterfall and terminal UI")
    add_rna_arguments(parser)
    parser.add_argument("--logbook", type=Path, help="SQLite reception log; w opens an explicit confirmation form")
    parser.add_argument("--log-event", choices=["CLE332"], help="tag new receptions for this event; omitted means general listening")
    parser.add_argument("--fixture", type=Path)
    parser.add_argument("--config", type=Path)
    parser.add_argument("--allow-live", action="store_true")
    parser.add_argument("--receiver", help="live receiver host[:port]; local receivers only by policy")
    parser.add_argument("--audio", action="store_true", help="enable local audio instead of a null sink")
    parser.add_argument("--presets", type=Path, default=Path("presets.toml"))
    parser.add_argument("--rows", type=int, default=400)
    parser.add_argument("--repeat", type=int, default=200)
    parser.add_argument("--fps", type=float, default=20.0)
    parser.add_argument("--refresh-hz", type=float, default=20.0,
                        help="maximum display refresh rate (default: 20 Hz; does not change receiver cadence)")
    parser.add_argument("--main-step-khz", type=float, help="override remembered step pair (fallback: 1 kHz)")
    parser.add_argument("--small-step-khz", type=float, help="override remembered step pair (fallback: 0.1 kHz)")
    parser.add_argument("--render-min-db", type=float, help="override remembered scale minimum (fallback: -100 dB)")
    parser.add_argument("--render-max-db", type=float, help="override remembered scale maximum (fallback: -40 dB)")
    parser.add_argument("--auto-scale", action=argparse.BooleanOptionalAction, default=None,
                        help="override remembered automatic/manual display scaling")
    parser.add_argument("--scale-font", choices=("auto", "pillow", "bitmap"), default="auto")
    parser.add_argument("--scale-font-name", default="DejaVuSansMono.ttf")
    parser.add_argument('--show-cw-offset-marker', action='store_true', help='show the normally hidden CW receiver-reference mark; display only')
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--demo-seconds", type=float, help="exit cleanly after a fixture demonstration interval")
    parser.add_argument("--dry-run", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)
    explicit_steps = args.main_step_khz is not None or args.small_step_khz is not None
    args.main_step_khz = 1.0 if args.main_step_khz is None else args.main_step_khz
    args.small_step_khz = 0.1 if args.small_step_khz is None else args.small_step_khz
    try:
        if args.fps <= 0 or args.refresh_hz <= 0:
            raise ValueError("FPS and refresh rate must be positive")
        if args.main_step_khz <= 0 or args.small_step_khz <= 0:
            raise ValueError("frequency steps must be positive")
        if args.demo_seconds is not None and args.demo_seconds <= 0:
            raise ValueError("demo seconds must be positive")
        if args.fixture is not None and args.allow_live:
            raise ValueError("choose either --fixture or --allow-live")
        if args.fixture is None and not args.allow_live:
            raise ValueError("provide --fixture or explicit --allow-live")
        if args.logbook is not None and args.rna is None:
            raise ValueError("--logbook requires --rna")
        if args.log_event is not None and args.logbook is None:
            raise ValueError("--log-event requires --logbook")
        rna_browser = browser_from_args(args)
        presenter = KittyPanePresenter(output=sys.stdout.buffer, force=args.force)
        if args.fixture is not None:
            levels = WaterfallLevelController(
                min_dbm=-100 if args.render_min_db is None else args.render_min_db,
                max_dbm=-40 if args.render_max_db is None else args.render_max_db,
                automatic=False if args.auto_scale is None else args.auto_scale,
            )
            model = WaterfallGuiModel(
                history_rows=args.rows,
                show_frequency_lines=False,
                render_min_db=levels.min_dbm,
                render_max_db=levels.max_dbm,
                main_step_hz=args.main_step_khz * 1000.0,
                small_step_hz=args.small_step_khz * 1000.0,
            )
            timeline = FixtureWaterfallTimeline.from_fixture(args.fixture, repeat=args.repeat)
            presets = load_presets_file(args.presets)["presets"]
            if rna_browser is not None:
                rna_browser.set_receiver("fixture", model.session.state.frequency_khz)
            if args.dry_run:
                timeline.advance(model.publisher)
                start_khz, end_khz = model.display_frequency_range()
                print(json.dumps({
                    "backend": "kitty+curses",
                    "fixture_frames": timeline.total_frames,
                    "rna": None if rna_browser is None else rna_browser.status(),
                    "frequency": [start_khz, end_khz],
                    "presets_visible": format_preset_ruler(presets, start_khz, end_khz, columns=120).strip(),
                    "network": False,
                    "steps_khz": [args.main_step_khz, args.small_step_khz],
                }, indent=2, sort_keys=True))
                return 0
            curses.wrapper(
                lambda screen: run_fixture_shell(
                    screen,
                    model=model,
                    rna_browser=rna_browser,
                    logbook_path=args.logbook,
                    log_event=args.log_event,
                    timeline=timeline,
                    live_source=None,
                    presets=presets,
                    presenter=presenter,
                    levels=levels,
                    tui_controller=None,
                    tui_config=None,
                    show_cw_offset_marker=args.show_cw_offset_marker,
                    source_fps=args.fps,
                    refresh_hz=args.refresh_hz,
                    scale_font_backend=args.scale_font,
                    scale_font_name=args.scale_font_name,
                    demo_seconds=args.demo_seconds,
                )
            )
            return 0

        from kiwi_client.client_app import ClientController, normalize_receiver_address
        from kiwi_client.config import discover_config_path, load_config
        from kiwi_client.tui import startup_receiver_presets, startup_state_and_presets

        config = load_config(discover_config_path(args.config))
        scale = startup_waterfall_scale(config)
        for key, value in (('min_dbm', args.render_min_db), ('max_dbm', args.render_max_db),
                           ('automatic', args.auto_scale)):
            if value is not None:
                scale[key] = value
        levels = WaterfallLevelController(**scale)
        state, presets = startup_state_and_presets(config)
        state = normalize_console_cw_bandwidth(state)
        if args.receiver:
            host, port = normalize_receiver_address(args.receiver, default_port=state.port)
            state = replace(state, host=host, port=port)
        mode = state.mode.lower()
        if explicit_steps or mode not in state.mode_step_indices:
            pairs = state.mode_step_pairs.get(mode, ((args.main_step_khz * 1000.0, args.small_step_khz * 1000.0),))
            step_index = nearest_step_pair_index(
                pairs,
                main_hz=args.main_step_khz * 1000.0,
                small_hz=args.small_step_khz * 1000.0,
            )
            state = replace(state, mode_step_indices={**state.mode_step_indices, mode: step_index})
        controller = ClientController(
            state=state,
            allow_live_default=config.live.allow_live,
            presets=presets,
            receiver_presets=startup_receiver_presets(config),
        )
        controller.configure_waterfall_session(
            center_khz=state.frequency_khz,
            zoom=startup_waterfall_zoom(config),
            speed=config.waterfall.speed,
            interp=config.waterfall.interp,
            history_rows=args.rows,
        )
        model = WaterfallGuiModel(
            history_rows=args.rows,
            show_frequency_lines=False,
            render_min_db=levels.min_dbm,
            render_max_db=levels.max_dbm,
            tuned_khz=state.frequency_khz,
            selected_khz=state.frequency_khz,
            mode=state.mode,
            low_cut_hz=state.low_cut_hz,
            high_cut_hz=state.high_cut_hz,
            main_step_hz=state.current_step_hz,
            small_step_hz=state.current_small_step_hz,
            frequency_decimals=config.display.frequency_decimals,
        )
        source = ControllerConsoleSource(controller, model=model, audio=args.audio)
        if rna_browser is not None:
            rna_browser.set_receiver(state.receiver, state.frequency_khz)
        if args.dry_run:
            print(json.dumps({
                "backend": "kitty+curses",
                "receiver": state.receiver,
                "waterfall_zoom": controller.paired_session.state.waterfall_zoom,
                "waterfall_scale": scale,
                "passband_hz": [state.low_cut_hz, state.high_cut_hz],
                "rna": None if rna_browser is None else rna_browser.status(),
                "audio": args.audio,
                "network": False,
                "steps_khz": [state.current_step_hz / 1000.0, state.current_small_step_hz / 1000.0],
                "would_start": "radio-bg --allow-live" + ("" if args.audio else " --null-sink"),
            }, indent=2, sort_keys=True))
            return 0
        source.start()
        try:
            curses.wrapper(
                lambda screen: run_fixture_shell(
                    screen,
                    model=model,
                    rna_browser=rna_browser,
                    logbook_path=args.logbook,
                    log_event=args.log_event,
                    timeline=None,
                    live_source=source,
                    presets=controller.presets,
                    presenter=presenter,
                    levels=levels,
                    tui_controller=controller,
                    tui_config=config,
                    settings_checkpoint=ConsoleSettingsCheckpoint(config),
                    show_cw_offset_marker=args.show_cw_offset_marker,
                    source_fps=args.fps,
                    refresh_hz=args.refresh_hz,
                    scale_font_backend=args.scale_font,
                    scale_font_name=args.scale_font_name,
                    demo_seconds=args.demo_seconds,
                )
            )
        finally:
            source.stop()
        return 0
    except (OSError, RuntimeError, ValueError) as exc:
        raise SystemExit(f"kiwi-console: error: {exc}") from exc


if __name__ == "__main__":
    raise SystemExit(main())
