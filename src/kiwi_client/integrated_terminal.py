"""Fixture-first integrated curses and Kitty waterfall shell."""

from __future__ import annotations

import argparse
import curses
import json
import os
import sys
import time
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any, BinaryIO, Mapping

from kiwi_client.gui_app import FixtureWaterfallTimeline, WaterfallGuiModel
from kiwi_client.state_store import load_presets_file
from kiwi_client.tui import InputMode, TuiInputState, handle_tui_key, render_tui_hints
from kiwi_client.waterfall_levels import WaterfallLevelController
from kiwi_client.waterfall_raster import RasterImage, encode_png
from kiwi_client.waterfall_scale import compose_waterfall_scale
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
        self._last_key: tuple[int, int, int] | None = None
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
        key = None if generation is None else (generation, layout.columns, layout.waterfall_rows)
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
    demo_seconds: float | None = None,
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
    pending_preset = False
    tui_input = TuiInputState() if tui_controller is not None and tui_config is not None else None
    last_response = None
    message = "live paired session starting" if live_source is not None else "fixture-only; no receiver connection"

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
            if timeline is not None and now >= next_source and not timeline.done:
                timeline.advance(model.publisher)
                next_source = now + 1.0 / source_fps
                dirty = True
            elif live_source is not None:
                if live_source.poll_generation() or now >= next_source:
                    next_source = now + 0.25
                    dirty = True

            try:
                key = screen.get_wch()
            except curses.error:
                key = None
            key = discard_console_mouse_event(key)
            if key == curses.KEY_RESIZE:
                presenter.invalidate()
                full_redraw = True
                dirty = True
            elif entry is not None and key is not None:
                if key in ("\n", "\r"):
                    try:
                        model.set_tuned_frequency(float(entry))
                        message = f"frequency {entry} kHz (local fixture state)"
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
            elif key in ("h", curses.KEY_LEFT):
                model.move_selection(-1)
                presenter.invalidate()
                dirty = True
            elif key in ("l", curses.KEY_RIGHT):
                model.move_selection(1)
                presenter.invalidate()
                dirty = True
            elif key == "H":
                model.move_selection(-1, small=True)
                presenter.invalidate()
                dirty = True
            elif key == "L":
                model.move_selection(1, small=True)
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
                        low_cut_hz=state.low_cut_hz,
                        high_cut_hz=state.high_cut_hz,
                        presets=presets,
                        font_backend=scale_font_backend,
                        font_name=scale_font_name,
                    ).image
                _safe_line(screen, layout.divider_row, "─" * columns, columns, curses.A_DIM)
                if entry is not None:
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
                rows = [
                    f"{state.mode.upper()} tuned {state.frequency_khz:.3f} kHz | selected {state.selected_khz:.3f} kHz | step {model.main_step_hz / 1000:g}/{model.small_step_hz / 1000:g} kHz | zoom {state.waterfall_zoom} | audio {'ON' if state.audio_enabled else 'MUTED'}",
                    f"{format_rssi_indicator(metrics.get('rssi_db'))} | volume {tui_controller.state.volume_percent if tui_controller is not None else 0}% | W/F {0 if snapshot is None else snapshot.generation}/{model.rasterizer.presented_generation}",
                    f"{levels.status_text()} | {transport_status}",
                    f"Message: {message}",
                    "h/l select H/L fine t/T step m mode Enter tune c center +/- zoom f freq p preset a audio k/j vol u auto q quit",
                    prompt,
                ]
                if tui_input is not None and tui_config is not None:
                    rows.extend(render_tui_hints(tui_input, tui_config, tui_controller).splitlines())
                for offset, text in enumerate(rows[:layout.tui_rows]):
                    _safe_line(screen, layout.tui_top + offset, text, columns)
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


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Fixture-first integrated Kitty waterfall and terminal UI")
    parser.add_argument("--fixture", type=Path)
    parser.add_argument("--config", type=Path)
    parser.add_argument("--allow-live", action="store_true")
    parser.add_argument("--receiver", help="live receiver host[:port]; local receivers only by policy")
    parser.add_argument("--audio", action="store_true", help="enable local audio instead of a null sink")
    parser.add_argument("--presets", type=Path, default=Path("presets.toml"))
    parser.add_argument("--rows", type=int, default=400)
    parser.add_argument("--repeat", type=int, default=200)
    parser.add_argument("--fps", type=float, default=20.0)
    parser.add_argument("--refresh-hz", type=float, default=5.0)
    parser.add_argument("--main-step-khz", type=float, default=1.0)
    parser.add_argument("--small-step-khz", type=float, default=0.1)
    parser.add_argument("--render-min-db", type=float, default=-100)
    parser.add_argument("--render-max-db", type=float, default=-40)
    parser.add_argument("--auto-scale", action="store_true", help="percentile-based smoothed display levels")
    parser.add_argument("--scale-font", choices=("auto", "pillow", "bitmap"), default="auto")
    parser.add_argument("--scale-font-name", default="DejaVuSansMono.ttf")
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--demo-seconds", type=float, help="exit cleanly after a fixture demonstration interval")
    parser.add_argument("--dry-run", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)
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
        presenter = KittyPanePresenter(output=sys.stdout.buffer, force=args.force)
        levels = WaterfallLevelController(
            min_dbm=args.render_min_db,
            max_dbm=args.render_max_db,
            automatic=args.auto_scale,
        )
        if args.fixture is not None:
            model = WaterfallGuiModel(
                history_rows=args.rows,
                show_frequency_lines=False,
                render_min_db=args.render_min_db,
                render_max_db=args.render_max_db,
                main_step_hz=args.main_step_khz * 1000.0,
                small_step_hz=args.small_step_khz * 1000.0,
            )
            timeline = FixtureWaterfallTimeline.from_fixture(args.fixture, repeat=args.repeat)
            presets = load_presets_file(args.presets)["presets"]
            if args.dry_run:
                timeline.advance(model.publisher)
                start_khz, end_khz = model.display_frequency_range()
                print(json.dumps({
                    "backend": "kitty+curses",
                    "fixture_frames": timeline.total_frames,
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
                    timeline=timeline,
                    live_source=None,
                    presets=presets,
                    presenter=presenter,
                    levels=levels,
                    tui_controller=None,
                    tui_config=None,
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
        state, presets = startup_state_and_presets(config)
        if args.receiver:
            host, port = normalize_receiver_address(args.receiver, default_port=state.port)
            state = replace(state, host=host, port=port)
        mode = state.mode.lower()
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
            center_khz=config.waterfall.center_khz,
            zoom=config.waterfall.zoom,
            speed=config.waterfall.speed,
            interp=config.waterfall.interp,
            history_rows=args.rows,
        )
        model = WaterfallGuiModel(
            history_rows=args.rows,
            show_frequency_lines=False,
            render_min_db=args.render_min_db,
            render_max_db=args.render_max_db,
            tuned_khz=state.frequency_khz,
            selected_khz=state.frequency_khz,
            mode=state.mode,
            low_cut_hz=state.low_cut_hz,
            high_cut_hz=state.high_cut_hz,
            main_step_hz=args.main_step_khz * 1000.0,
            small_step_hz=args.small_step_khz * 1000.0,
            frequency_decimals=config.display.frequency_decimals,
        )
        source = ControllerConsoleSource(controller, model=model, audio=args.audio)
        if args.dry_run:
            print(json.dumps({
                "backend": "kitty+curses",
                "receiver": state.receiver,
                "audio": args.audio,
                "network": False,
                "steps_khz": [args.main_step_khz, args.small_step_khz],
                "would_start": "radio-bg --allow-live" + ("" if args.audio else " --null-sink"),
            }, indent=2, sort_keys=True))
            return 0
        source.start()
        try:
            curses.wrapper(
                lambda screen: run_fixture_shell(
                    screen,
                    model=model,
                    timeline=None,
                    live_source=source,
                    presets=controller.presets,
                    presenter=presenter,
                    levels=levels,
                    tui_controller=controller,
                    tui_config=config,
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
