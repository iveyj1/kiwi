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
from kiwi_client.waterfall_raster import CURSOR_MARKER_RGB, RasterImage, encode_png
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
    passband_row: int
    frequency_row: int
    preset_row: int
    divider_row: int
    tui_top: int
    tui_rows: int

    @classmethod
    def compute(cls, *, columns: int, lines: int) -> "IntegratedTerminalLayout":
        if columns < 40 or lines < 12:
            raise ValueError("integrated terminal requires at least 40 columns and 12 lines")
        waterfall_rows = lines // 2
        passband_row = waterfall_rows
        frequency_row = passband_row + 1
        preset_row = frequency_row + 1
        divider_row = preset_row + 1
        tui_top = divider_row + 1
        return cls(
            columns=columns,
            lines=lines,
            waterfall_top=0,
            waterfall_rows=waterfall_rows,
            passband_row=passband_row,
            frequency_row=frequency_row,
            preset_row=preset_row,
            divider_row=divider_row,
            tui_top=tui_top,
            tui_rows=lines - tui_top,
        )


PASSBAND_SCALE_RGB = (0, 255, 0)


def append_tuning_strip(
    image: RasterImage,
    start_khz: float,
    end_khz: float,
    *,
    tuned_khz: float,
    selected_khz: float,
    low_cut_hz: int,
    high_cut_hz: int,
    height: int = 8,
) -> RasterImage:
    """Append a high-resolution Kiwi-style passband/selection strip below W/F data."""
    if height < 6 or end_khz <= start_khz:
        raise ValueError("tuning strip requires height >= 6 and a positive frequency span")
    strip = bytearray(image.width * height * 3)

    def column(frequency_khz: float) -> int | None:
        if not start_khz <= frequency_khz <= end_khz:
            return None
        return round((frequency_khz - start_khz) / (end_khz - start_khz) * (image.width - 1))

    def pixel(x: int, y: int, color: tuple[int, int, int]) -> None:
        offset = (y * image.width + x) * 3
        strip[offset:offset + 3] = bytes(color)

    low = column(tuned_khz + low_cut_hz / 1000.0)
    center = column(tuned_khz)
    high = column(tuned_khz + high_cut_hz / 1000.0)
    if low is not None and high is not None:
        low, high = sorted((low, high))
        for x in range(low, high + 1):
            for y in (2, 3):
                pixel(x, y, PASSBAND_SCALE_RGB)
        for x in range(low, min(image.width, low + 2)):
            for y in range(0, 4):
                pixel(x, y, PASSBAND_SCALE_RGB)
        for x in range(max(0, high - 1), high + 1):
            for y in range(0, 4):
                pixel(x, y, PASSBAND_SCALE_RGB)
    if center is not None:
        for x in range(center, min(image.width, center + 2)):
            for y in range(2, height - 1):
                pixel(x, y, PASSBAND_SCALE_RGB)
    selected = column(selected_khz)
    if selected is not None and selected != center:
        for radius in range(3):
            y = height - 1 - radius
            for x in range(max(0, selected - radius), min(image.width, selected + radius + 1)):
                pixel(x, y, CURSOR_MARKER_RGB)
    return RasterImage(image.width, image.height + height, image.rgb + bytes(strip))


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
        self.model.publisher = self.controller.waterfall_snapshots
        self.model.session = self.controller.paired_session
        self.model.action_dispatch = self.controller.dispatch_session_action
        self.model._session_mapped = True
        self.started = True

    def poll_generation(self) -> int:
        sync_status = getattr(self.controller, "paired_session_status", None)
        if sync_status is not None:
            sync_status()
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
        self.image_id = image_id
        self.placement_id = placement_id
        self.force = force
        self.environ = os.environ if environ is None else environ
        self._last_key: tuple[int, int, int] | None = None
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
        payload = encode_kitty_image(
            encode_png(image),
            image_id=self.image_id,
            placement_id=self.placement_id,
            columns=layout.columns,
            rows=layout.waterfall_rows,
        )
        position = f"\x1b[{layout.waterfall_top + 1};1H".encode("ascii")
        self.output.write(b"\x1b7" + position + payload + b"\x1b8")
        flush = getattr(self.output, "flush", None)
        if flush is not None:
            flush()
        self._last_key = key
        return True

    def invalidate(self) -> None:
        self._last_key = None

    def finish(self) -> None:
        if self._finished:
            return
        self.output.write(f"\x1b_Ga=d,d=i,i={self.image_id},q=2;\x1b\\".encode("ascii"))
        flush = getattr(self.output, "flush", None)
        if flush is not None:
            flush()
        self._finished = True


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
    source_fps: float,
    refresh_hz: float,
    demo_seconds: float | None = None,
) -> None:
    """Run fixture publication, curses text, and Kitty presentation in one thread."""
    screen.nodelay(True)
    screen.keypad(True)
    try:
        curses.curs_set(0)
    except curses.error:
        pass
    preset_attributes = 0
    if curses.has_colors():
        curses.start_color()
        curses.use_default_colors()
        curses.init_pair(1, curses.COLOR_CYAN, -1)
        preset_attributes = curses.color_pair(1)
    if (timeline is None) == (live_source is None):
        raise ValueError("console requires exactly one fixture or live source")
    if timeline is not None:
        timeline.advance(model.publisher)
    started = time.monotonic()
    next_source = started
    next_refresh = 0.0
    dirty = True
    entry: str | None = None
    pending_preset = False
    message = "live paired session starting" if live_source is not None else "fixture-only; no receiver connection"

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
            if key == curses.KEY_RESIZE:
                presenter.invalidate()
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
                break
            elif key == "f":
                entry = ""
                dirty = True
            elif key == "p":
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
                screen.erase()
                state = model.session.state
                if live_source is not None:
                    message = f"live SND {state.snd_status} / W/F {state.wf_status}"
                    if state.error is not None:
                        message += f" | {state.error.stream}: {state.error.message}"
                image = None
                if snapshot is None:
                    _safe_line(screen, layout.passband_row, "Waiting for first W/F frame...", columns)
                    _safe_line(screen, layout.frequency_row, "", columns)
                    _safe_line(screen, layout.preset_row, "", columns)
                else:
                    image = model.image()
                    start_khz, end_khz = model.display_frequency_range()
                    image = append_tuning_strip(
                        image,
                        start_khz,
                        end_khz,
                        tuned_khz=state.frequency_khz,
                        selected_khz=state.selected_khz,
                        low_cut_hz=state.low_cut_hz,
                        high_cut_hz=state.high_cut_hz,
                    )
                    frequency_marks, frequency_labels = format_frequency_tick_ruler(
                        start_khz,
                        end_khz,
                        columns=columns,
                    )
                    _safe_line(
                        screen,
                        layout.passband_row,
                        frequency_marks,
                        columns,
                        curses.A_DIM,
                    )
                    _safe_line(
                        screen,
                        layout.frequency_row,
                        frequency_labels,
                        columns,
                    )
                    _safe_line(
                        screen,
                        layout.preset_row,
                        format_preset_ruler(presets, start_khz, end_khz, columns=columns),
                        columns,
                        preset_attributes,
                    )
                _safe_line(screen, layout.divider_row, "─" * columns, columns, curses.A_DIM)
                rows = [
                    f"{state.mode.upper()} tuned {state.frequency_khz:.3f} kHz | selected {state.selected_khz:.3f} kHz | zoom {state.waterfall_zoom}",
                    f"W/F source {0 if snapshot is None else snapshot.generation} presented {model.rasterizer.presented_generation} | {message}",
                    "h/l select  H/L fine  Enter tune  c center  +/- zoom  f frequency  p preset  q quit",
                    f"frequency kHz: {entry}_" if entry is not None else ("preset register: _" if pending_preset else ":"),
                ]
                for offset, text in enumerate(rows[:layout.tui_rows]):
                    _safe_line(screen, layout.tui_top + offset, text, columns)
                screen.noutrefresh()
                curses.doupdate()
                if image is not None and snapshot is not None:
                    presenter.draw(image, layout, generation=snapshot.generation)
                next_refresh = now + 1.0 / refresh_hz
                dirty = False
            time.sleep(0.005)
    finally:
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
    parser.add_argument("--render-min-db", type=float, default=-100)
    parser.add_argument("--render-max-db", type=float, default=-40)
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--demo-seconds", type=float, help="exit cleanly after a fixture demonstration interval")
    parser.add_argument("--dry-run", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)
    try:
        if args.fps <= 0 or args.refresh_hz <= 0:
            raise ValueError("FPS and refresh rate must be positive")
        if args.demo_seconds is not None and args.demo_seconds <= 0:
            raise ValueError("demo seconds must be positive")
        if args.fixture is not None and args.allow_live:
            raise ValueError("choose either --fixture or --allow-live")
        if args.fixture is None and not args.allow_live:
            raise ValueError("provide --fixture or explicit --allow-live")
        presenter = KittyPanePresenter(output=sys.stdout.buffer, force=args.force)
        if args.fixture is not None:
            model = WaterfallGuiModel(
                history_rows=args.rows,
                show_frequency_lines=False,
                render_min_db=args.render_min_db,
                render_max_db=args.render_max_db,
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
                    source_fps=args.fps,
                    refresh_hz=args.refresh_hz,
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
            main_step_hz=state.current_step_hz,
            small_step_hz=state.current_small_step_hz,
            frequency_decimals=config.display.frequency_decimals,
        )
        source = ControllerConsoleSource(controller, model=model, audio=args.audio)
        if args.dry_run:
            print(json.dumps({
                "backend": "kitty+curses",
                "receiver": state.receiver,
                "audio": args.audio,
                "network": False,
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
                    source_fps=args.fps,
                    refresh_hz=args.refresh_hz,
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
