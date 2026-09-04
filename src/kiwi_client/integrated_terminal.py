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
from kiwi_client.waterfall_raster import RasterImage, encode_png
from kiwi_client.waterfall_terminal import encode_kitty_image, format_frequency_ruler, terminal_supports_kitty


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


def format_passband_scale(
    start_khz: float,
    end_khz: float,
    *,
    tuned_khz: float,
    selected_khz: float,
    low_cut_hz: int,
    high_cut_hz: int,
    columns: int,
) -> str:
    """Render a Kiwi-style passband bracket and selection pointer outside the raster."""
    if columns <= 0 or end_khz <= start_khz:
        raise ValueError("passband scale requires positive columns and frequency span")
    scale = [" "] * columns

    def position(frequency_khz: float) -> int | None:
        if not start_khz <= frequency_khz <= end_khz:
            return None
        return round((frequency_khz - start_khz) / (end_khz - start_khz) * (columns - 1))

    low = position(tuned_khz + low_cut_hz / 1000.0)
    center = position(tuned_khz)
    high = position(tuned_khz + high_cut_hz / 1000.0)
    if low is not None and high is not None:
        low, high = sorted((low, high))
        if high > low:
            for column in range(low + 1, high):
                scale[column] = "─"
            scale[low] = "└"
            scale[high] = "┘"
            if center is not None and low < center < high:
                scale[center] = "┴"
    elif center is not None:
        scale[center] = "┴"
    selected = position(selected_khz)
    if selected is not None and (center is None or selected != center):
        scale[selected] = "▼"
    return "".join(scale)


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
            candidates.append((frequency_khz, f"|{register} {frequency_khz:.3f}"))
    for frequency_khz, label in sorted(candidates):
        label = label[:columns]
        position = round((frequency_khz - start_khz) / span * (columns - 1))
        start = min(max(0, position - len(label) // 2), columns - len(label))
        stop = start + len(label)
        if any(start < used_stop + 1 and stop + 1 > used_start for used_start, used_stop in occupied):
            continue
        ruler[start:stop] = label
        occupied.append((start, stop))
    return "".join(ruler)


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
    model.set_direct_frequency(float(preset["frequency_khz"]))
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
    timeline: FixtureWaterfallTimeline,
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
    passband_attributes = 0
    preset_attributes = 0
    if curses.has_colors():
        curses.start_color()
        curses.use_default_colors()
        curses.init_pair(1, curses.COLOR_GREEN, -1)
        curses.init_pair(2, curses.COLOR_CYAN, -1)
        passband_attributes = curses.color_pair(1) | curses.A_BOLD
        preset_attributes = curses.color_pair(2)
    timeline.advance(model.publisher)
    started = time.monotonic()
    next_source = started
    next_refresh = 0.0
    dirty = True
    entry: str | None = None
    pending_preset = False
    message = "fixture-only; no receiver connection"

    try:
        while True:
            now = time.monotonic()
            if demo_seconds is not None and now - started >= demo_seconds:
                break
            if now >= next_source and not timeline.done:
                timeline.advance(model.publisher)
                next_source = now + 1.0 / source_fps
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
                        model.set_direct_frequency(float(entry))
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
                image = model.image()
                start_khz, end_khz = model.display_frequency_range()
                screen.erase()
                state = model.session.state
                _safe_line(
                    screen,
                    layout.passband_row,
                    format_passband_scale(
                        start_khz,
                        end_khz,
                        tuned_khz=state.frequency_khz,
                        selected_khz=state.selected_khz,
                        low_cut_hz=state.low_cut_hz,
                        high_cut_hz=state.high_cut_hz,
                        columns=columns,
                    ),
                    columns,
                    passband_attributes,
                )
                _safe_line(
                    screen,
                    layout.frequency_row,
                    format_frequency_ruler(start_khz, end_khz, columns=columns),
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
                    f"W/F source {model.publisher.latest().generation} presented {model.rasterizer.presented_generation} | {message}",
                    "h/l select  H/L fine  Enter tune  c center  +/- zoom  f frequency  p preset  q quit",
                    f"frequency kHz: {entry}_" if entry is not None else ("preset register: _" if pending_preset else ":"),
                ]
                for offset, text in enumerate(rows[:layout.tui_rows]):
                    _safe_line(screen, layout.tui_top + offset, text, columns)
                screen.noutrefresh()
                curses.doupdate()
                presenter.draw(image, layout, generation=model.publisher.latest().generation)
                next_refresh = now + 1.0 / refresh_hz
                dirty = False
            time.sleep(0.005)
    finally:
        presenter.finish()


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Fixture-first integrated Kitty waterfall and terminal UI")
    parser.add_argument("--fixture", type=Path, required=True)
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
        presenter = KittyPanePresenter(output=sys.stdout.buffer, force=args.force)
        curses.wrapper(
            lambda screen: run_fixture_shell(
                screen,
                model=model,
                timeline=timeline,
                presets=presets,
                presenter=presenter,
                source_fps=args.fps,
                refresh_hz=args.refresh_hz,
                demo_seconds=args.demo_seconds,
            )
        )
        return 0
    except (OSError, RuntimeError, ValueError) as exc:
        raise SystemExit(f"kiwi-console: error: {exc}") from exc


if __name__ == "__main__":
    raise SystemExit(main())
