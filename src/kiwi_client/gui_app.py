"""Fixture-first native PySide6 waterfall prototype."""

from __future__ import annotations

import argparse
import json
from collections import deque
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any, Callable

from kiwi_client.fixtures import load_jsonl_events
from kiwi_client.protocol import parse_msg
from kiwi_client.waterfall import (
    WaterfallFrame,
    WaterfallReceiverState,
    contextualize_waterfall_frame,
    parse_waterfall_uncompressed,
)
from kiwi_client.session_manager import (
    DirectFrequency,
    RadioSessionManager,
    RadioSessionSnapshot,
    RecenterWaterfall,
    SelectFrequency,
    ToggleAudio,
    TuneSelected,
    ZoomWaterfall,
)
from kiwi_client.waterfall_raster import (
    RasterImage,
    WaterfallOverlay,
    apply_frequency_overlay,
    render_dbm_rows,
)
from kiwi_client.waterfall_snapshots import WaterfallSnapshot, WaterfallSnapshotPublisher


def logical_display_height(
    source_rows: int,
    *,
    row_pixels: float = 1.0,
    device_pixel_ratio: float = 1.0,
    available_logical_height: int | None = None,
) -> int:
    """Map source rows to DPI-aware logical height, capped by screen space."""
    if source_rows <= 0 or row_pixels <= 0 or device_pixel_ratio <= 0:
        raise ValueError("source rows, row pixels and device pixel ratio must be positive")
    height = max(1, round(source_rows * row_pixels / device_pixel_ratio))
    if available_logical_height is not None:
        if available_logical_height <= 0:
            raise ValueError("available logical height must be positive")
        height = min(height, available_logical_height)
    return height


def gui_focus_target(event: str) -> str:
    """Return the intended focus owner for a GUI lifecycle/input event."""
    if event == "frequency_requested":
        return "frequency"
    if event in ("startup", "frequency_accepted"):
        return "display"
    raise ValueError(f"unknown GUI focus event: {event}")


def gui_control_action(key: str, *, shift: bool = False) -> tuple[str, int, bool] | None:
    """Map toolkit-neutral keys to local fixture control actions."""
    normalized = key.lower()
    if normalized in ("left", "h"):
        return ("move", -1, shift or key == "H")
    if normalized in ("right", "l"):
        return ("move", 1, shift or key == "L")
    if normalized in ("enter", "return"):
        return ("tune", 0, False)
    if normalized == "c":
        return ("recenter", 0, False)
    if normalized in ("+", "="):
        return ("zoom", 1, False)
    if normalized == "-":
        return ("zoom", -1, False)
    return None


def gui_close_key(key: str, *, control: bool = False) -> bool:
    """Return whether a toolkit-neutral key description closes the GUI."""
    normalized = key.lower()
    return normalized == "escape" or normalized == "q"


def load_fixture_frames(path: Path) -> tuple[WaterfallFrame, ...]:
    """Decode and contextualize W/F fixture frames without a UI dependency."""
    state = WaterfallReceiverState()
    frames: list[WaterfallFrame] = []
    for event in load_jsonl_events(path):
        if event.dir != "rx" or event.stream != "wf":
            continue
        if event.type == "msg":
            state = state.apply_msg_params(parse_msg(event.raw["text"]).params)
        elif event.type == "binary":
            frames.append(
                contextualize_waterfall_frame(
                    parse_waterfall_uncompressed(event.binary_payload),
                    state,
                )
            )
    return tuple(frames)


@dataclass
class FixtureWaterfallTimeline:
    """Incrementally publish a finite repeated fixture sequence."""

    frames: tuple[WaterfallFrame, ...]
    repeat: int = 1
    index: int = 0

    def __post_init__(self) -> None:
        if not self.frames:
            raise ValueError("fixture contains no W/F frames")
        if self.repeat <= 0:
            raise ValueError("fixture repeat must be positive")

    @classmethod
    def from_fixture(cls, path: Path, *, repeat: int = 1) -> "FixtureWaterfallTimeline":
        return cls(load_fixture_frames(path), repeat=repeat)

    @property
    def total_frames(self) -> int:
        return len(self.frames) * self.repeat

    @property
    def done(self) -> bool:
        return self.index >= self.total_frames

    def advance(self, publisher: WaterfallSnapshotPublisher) -> bool:
        if self.done:
            return False
        publisher.append(self.frames[self.index % len(self.frames)])
        self.index += 1
        return True


class SnapshotRasterizer:
    """Incrementally color only snapshot rows not presented previously."""

    def __init__(self, *, min_dbm: float, max_dbm: float) -> None:
        if max_dbm <= min_dbm:
            raise ValueError("render max dB must be greater than render min dB")
        self.min_dbm = min_dbm
        self.max_dbm = max_dbm
        self.presented_generation = 0
        self._width: int | None = None
        self._max_rows: int | None = None
        self._rgb_rows: deque[bytes] = deque()
        self._padding_rows: dict[int, bytes] = {}
        self._view: tuple[float, float] | None = None

    @staticmethod
    def _remap_row(
        row: bytes,
        width: int,
        *,
        source_start_khz: float,
        source_end_khz: float,
        target_start_khz: float,
        target_end_khz: float,
    ) -> bytes:
        if source_start_khz == target_start_khz and source_end_khz == target_end_khz:
            return row
        output = bytearray(width * 3)
        source_span = source_end_khz - source_start_khz
        target_span = target_end_khz - target_start_khz
        for column in range(width):
            frequency = target_start_khz + target_span * column / max(1, width - 1)
            source_column = round((frequency - source_start_khz) / source_span * (width - 1))
            if 0 <= source_column < width:
                source_offset = source_column * 3
                target_offset = column * 3
                output[target_offset:target_offset + 3] = row[source_offset:source_offset + 3]
        return bytes(output)

    def update(
        self,
        snapshot: WaterfallSnapshot,
        *,
        target_start_khz: float | None = None,
        target_end_khz: float | None = None,
    ) -> RasterImage:
        if target_start_khz is None or target_end_khz is None:
            view = None
        else:
            view = (target_start_khz, target_end_khz)
        view_changed = view != self._view
        if snapshot.generation > self.presented_generation or view_changed:
            delta = snapshot.generation - self.presented_generation
            rebuild = (
                self._width != snapshot.width
                or self._max_rows != snapshot.max_rows
                or delta > len(snapshot.rows)
                or not self._rgb_rows
                or view_changed
            )
            if rebuild:
                self._rgb_rows = deque(maxlen=snapshot.max_rows)
                new_rows = snapshot.rows
            else:
                new_rows = snapshot.rows[-delta:]
            self._width = snapshot.width
            self._max_rows = snapshot.max_rows
            for row in new_rows:
                rendered = render_dbm_rows((row.dbm,), min_dbm=self.min_dbm, max_dbm=self.max_dbm)
                rgb_row = rendered.rgb
                if view is not None and row.start_khz is not None and row.span_khz is not None:
                    rgb_row = self._remap_row(
                        rgb_row,
                        snapshot.width,
                        source_start_khz=row.start_khz,
                        source_end_khz=row.start_khz + row.span_khz,
                        target_start_khz=view[0],
                        target_end_khz=view[1],
                    )
                self._rgb_rows.append(rgb_row)
            self.presented_generation = snapshot.generation
            self._view = view

        if self._width is None or self._max_rows is None or not self._rgb_rows:
            raise ValueError("snapshot rasterizer has no rows")
        padding_count = self._max_rows - len(self._rgb_rows)
        if padding_count not in self._padding_rows:
            padding = render_dbm_rows(
                ((-255,) * self._width,),
                min_dbm=self.min_dbm,
                max_dbm=self.max_dbm,
            ).rgb
            self._padding_rows[padding_count] = padding * padding_count
        rgb = self._padding_rows[padding_count] + b"".join(self._rgb_rows)
        return RasterImage(self._width, self._max_rows, rgb)


@dataclass
class WaterfallGuiModel:
    """Renderer-neutral fixture model consumed by the first native window."""

    history_rows: int = 400
    render_min_db: float = -100
    render_max_db: float = -40
    tuned_khz: float | None = None
    selected_khz: float | None = None
    mode: str = "am"
    low_cut_hz: int = -5000
    high_cut_hz: int = 5000
    main_step_hz: float = 1000
    small_step_hz: float = 100
    frequency_decimals: int = 3
    show_frequency_lines: bool = True
    action_dispatch: Callable[[Any], Any] | None = None

    def __post_init__(self) -> None:
        if self.render_max_db <= self.render_min_db:
            raise ValueError("render_max_db must be greater than render_min_db")
        if self.main_step_hz <= 0 or self.small_step_hz <= 0:
            raise ValueError("GUI frequency steps must be positive")
        frequency = 5000.0 if self.tuned_khz is None else self.tuned_khz
        selected = frequency if self.selected_khz is None else self.selected_khz
        self.publisher = WaterfallSnapshotPublisher(max_rows=self.history_rows)
        self.rasterizer = SnapshotRasterizer(min_dbm=self.render_min_db, max_dbm=self.render_max_db)
        self.session = RadioSessionManager(
            RadioSessionSnapshot(
                frequency_khz=frequency,
                selected_khz=selected,
                mode=self.mode,
                low_cut_hz=self.low_cut_hz,
                high_cut_hz=self.high_cut_hz,
                frequency_decimals=self.frequency_decimals,
                waterfall_center_khz=frequency,
            )
        )
        self._session_mapped = False

    def bind_publisher(self, publisher: WaterfallSnapshotPublisher, *, preserve_session_view: bool = False) -> None:
        """Bind a replacement source and discard RGB history from the previous session."""
        self.publisher = publisher
        self.rasterizer = SnapshotRasterizer(min_dbm=self.render_min_db, max_dbm=self.render_max_db)
        self._session_mapped = preserve_session_view

    def set_render_scale(self, min_dbm: float, max_dbm: float) -> bool:
        """Change local display levels and invalidate cached RGB history."""
        if max_dbm <= min_dbm:
            raise ValueError("render max dB must be greater than render min dB")
        if min_dbm == self.render_min_db and max_dbm == self.render_max_db:
            return False
        self.render_min_db = min_dbm
        self.render_max_db = max_dbm
        self.rasterizer = SnapshotRasterizer(min_dbm=min_dbm, max_dbm=max_dbm)
        return True

    def load_fixture(self, path: Path, *, repeat: int = 1) -> int:
        timeline = FixtureWaterfallTimeline.from_fixture(path, repeat=repeat)
        while timeline.advance(self.publisher):
            pass
        return timeline.total_frames

    def _mapped_snapshot(self) -> WaterfallSnapshot:
        snapshot = self.publisher.latest()
        if snapshot is None:
            raise ValueError("waterfall GUI model has no frames")
        if not self._session_mapped:
            center = snapshot.current_center_khz
            if center is None and snapshot.current_start_khz is not None and snapshot.current_span_khz is not None:
                center = snapshot.current_start_khz + snapshot.current_span_khz / 2.0
            zoom = 0
            if snapshot.rows and snapshot.rows[-1].flags_x_zoom_server is not None:
                zoom = snapshot.rows[-1].flags_x_zoom_server & 0xFFFF
            state = self.session.state
            frequency = center if self.tuned_khz is None and center is not None else state.frequency_khz
            selected = frequency if self.selected_khz is None else state.selected_khz
            self.session.state = replace(
                state,
                frequency_khz=frequency,
                selected_khz=selected,
                waterfall_center_khz=center if center is not None else frequency,
                waterfall_zoom=zoom,
            )
            self._session_mapped = True
        return snapshot

    def display_frequency_range(self) -> tuple[float, float]:
        snapshot = self._mapped_snapshot()
        if snapshot.current_start_khz is None or snapshot.current_span_khz is None:
            raise ValueError("waterfall fixture has no frequency mapping")
        captured_zoom = 0
        if snapshot.rows and snapshot.rows[-1].flags_x_zoom_server is not None:
            captured_zoom = snapshot.rows[-1].flags_x_zoom_server & 0xFFFF
        state = self.session.state
        span_khz = snapshot.current_span_khz * (2.0 ** (captured_zoom - state.waterfall_zoom))
        center_khz = state.waterfall_center_khz
        return center_khz - span_khz / 2.0, center_khz + span_khz / 2.0

    def image(self) -> RasterImage:
        snapshot = self._mapped_snapshot()
        try:
            start_khz, end_khz = self.display_frequency_range()
        except ValueError:
            return self.rasterizer.update(snapshot)
        image = self.rasterizer.update(
            snapshot,
            target_start_khz=start_khz,
            target_end_khz=end_khz,
        )
        if not self.show_frequency_lines:
            return image
        state = self.session.state
        cursor_khz = state.selected_khz
        if abs(cursor_khz - state.frequency_khz) < 0.0000005:
            cursor_khz = None
        return apply_frequency_overlay(
            image,
            WaterfallOverlay(
                start_khz=start_khz,
                end_khz=end_khz,
                tuned_khz=state.frequency_khz,
                low_cut_hz=state.low_cut_hz,
                high_cut_hz=state.high_cut_hz,
                cursor_khz=cursor_khz,
                marker_width=2,
            ),
        )

    def _dispatch(self, action):
        if self.action_dispatch is not None:
            return self.action_dispatch(action)
        return self.session.dispatch(action)

    def move_selection(self, delta: int, *, small: bool = False, clamp_to_view: bool = True):
        snapshot = self._mapped_snapshot() if clamp_to_view else self.publisher.latest()
        step_hz = self.small_step_hz if small else self.main_step_hz
        frequency = self.session.state.selected_khz + delta * step_hz / 1000.0
        if snapshot is not None and clamp_to_view and snapshot.current_start_khz is not None and snapshot.current_span_khz is not None:
            start_khz, end_khz = self.display_frequency_range()
            frequency = min(max(frequency, start_khz), end_khz)
        return self._dispatch(SelectFrequency(frequency))

    def tune_selected(self):
        return self._dispatch(TuneSelected())

    def set_direct_frequency(self, frequency_khz: float):
        self._mapped_snapshot()
        return self._dispatch(DirectFrequency(frequency_khz))

    def set_tuned_frequency(self, frequency_khz: float):
        """Tune an entered frequency without implicitly recentering W/F."""
        self._mapped_snapshot()
        self._dispatch(SelectFrequency(frequency_khz))
        return self._dispatch(TuneSelected())

    def toggle_audio(self):
        self._mapped_snapshot()
        return self._dispatch(ToggleAudio())

    def recenter(self):
        self._mapped_snapshot()
        return self._dispatch(RecenterWaterfall())

    def zoom(self, delta: int):
        self._mapped_snapshot()
        return self._dispatch(ZoomWaterfall(delta))

    def frequency_text(self) -> str:
        try:
            start_khz, end_khz = self.display_frequency_range()
        except ValueError:
            return "Frequency mapping unavailable"
        return f"{start_khz:.4f} .. {end_khz:.4f} kHz"

    def status_text(self, *, requested_fps: float | None = None, ended: bool = False) -> str:
        snapshot = self.publisher.latest()
        if snapshot is None:
            return "source 0 | presented 0"
        state = self.session.state
        parts = [
            f"source {snapshot.generation}",
            f"presented {self.rasterizer.presented_generation}",
            f"{snapshot.width} bins",
            f"history {snapshot.max_rows} rows",
            f"tuned {state.frequency_khz:.4f} kHz",
            f"selected {state.selected_khz:.4f} kHz",
            f"zoom {state.waterfall_zoom}",
        ]
        if requested_fps is not None:
            parts.append(f"requested {requested_fps:g} FPS")
        if ended:
            parts.append("ended")
        return " | ".join(parts)

    def summary(
        self,
        *,
        animated: bool = False,
        requested_fps: float | None = None,
        requested_row_pixels: float = 1.0,
    ) -> dict:
        image = self.image()
        snapshot = self.publisher.latest()
        return {
            "backend": "PySide6",
            "frames": 0 if snapshot is None else snapshot.generation,
            "presented_generation": self.rasterizer.presented_generation,
            "image_width": image.width,
            "image_height": image.height,
            "frequency": self.frequency_text(),
            "status": self.status_text(requested_fps=requested_fps),
            "animated": animated,
            "requested_fps": requested_fps,
            "requested_row_pixels": requested_row_pixels,
            "session": self.session.state.as_dict(),
        }


def show_pyside_window(
    model: WaterfallGuiModel,
    *,
    timeline: FixtureWaterfallTimeline | None = None,
    fps: float = 20.0,
    row_pixels: float = 1.0,
) -> int:
    """Display direct-RGB fixture history, optionally publishing it on a timer."""
    try:
        from PySide6.QtCore import Qt, QTimer
        from PySide6.QtGui import QImage, QKeySequence, QPixmap, QShortcut
        from PySide6.QtWidgets import (
            QApplication,
            QHBoxLayout,
            QLabel,
            QLineEdit,
            QMainWindow,
            QPushButton,
            QSizePolicy,
            QVBoxLayout,
            QWidget,
        )
    except ImportError as exc:
        raise RuntimeError("native GUI requires: pip install -e '.[gui-pyside]'") from exc

    if fps <= 0:
        raise ValueError("GUI playback FPS must be positive")
    if row_pixels <= 0:
        raise ValueError("GUI row pixels must be positive")
    if timeline is not None and model.publisher.latest() is None:
        timeline.advance(model.publisher)

    app = QApplication.instance() or QApplication([])
    app.setQuitOnLastWindowClosed(True)
    window = QMainWindow()
    window.setWindowTitle("KiwiSDR Waterfall Prototype")
    central = QWidget()
    layout = QVBoxLayout(central)
    frequency = QLabel()
    frequency.setAlignment(Qt.AlignmentFlag.AlignCenter)
    display = QLabel()
    display.setMinimumWidth(640)
    display.setScaledContents(True)
    display.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
    display.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
    screen = app.primaryScreen()
    device_pixel_ratio = screen.devicePixelRatio() if screen is not None else 1.0
    available_height = max(1, screen.availableGeometry().height() - 140) if screen is not None else None
    display_height = logical_display_height(
        model.history_rows,
        row_pixels=row_pixels,
        device_pixel_ratio=device_pixel_ratio,
        available_logical_height=available_height,
    )
    display.setFixedHeight(display_height)
    effective_row_pixels = display_height * device_pixel_ratio / model.history_rows
    status = QLabel()
    status.setAlignment(Qt.AlignmentFlag.AlignCenter)
    controls = QHBoxLayout()
    frequency_entry = QLineEdit()
    frequency_entry.setPlaceholderText("Frequency kHz")
    apply_frequency = QPushButton("Set frequency")
    tune_button = QPushButton("Tune selected")
    center_button = QPushButton("Center")
    zoom_out_button = QPushButton("Zoom -")
    zoom_in_button = QPushButton("Zoom +")
    controls.addWidget(frequency_entry, 1)
    for button in (apply_frequency, tune_button, center_button, zoom_out_button, zoom_in_button):
        controls.addWidget(button)

    def update_display(*, ended: bool = False) -> None:
        image = model.image()
        qimage = QImage(
            image.rgb,
            image.width,
            image.height,
            image.width * 3,
            QImage.Format.Format_RGB888,
        )
        display.setPixmap(QPixmap.fromImage(qimage))
        frequency.setText(model.frequency_text())
        base_status = model.status_text(requested_fps=fps if timeline is not None else None, ended=ended)
        status.setText(f"{base_status} | display {effective_row_pixels:.2f} px/frame")

    def apply_direct_frequency() -> None:
        try:
            model.set_direct_frequency(float(frequency_entry.text()))
        except ValueError as exc:
            status.setText(f"Frequency error: {exc}")
            return
        update_display()
        display.setFocus()

    def run_action(action) -> None:
        action()
        update_display()

    apply_frequency.clicked.connect(apply_direct_frequency)
    frequency_entry.returnPressed.connect(apply_direct_frequency)
    tune_button.clicked.connect(lambda: run_action(model.tune_selected))
    center_button.clicked.connect(lambda: run_action(model.recenter))
    zoom_out_button.clicked.connect(lambda: run_action(lambda: model.zoom(-1)))
    zoom_in_button.clicked.connect(lambda: run_action(lambda: model.zoom(1)))

    update_display()
    layout.addWidget(frequency)
    layout.addWidget(display, 1)
    layout.addLayout(controls)
    layout.addWidget(status)
    window.setCentralWidget(central)
    window.resize(1200, display_height + 120)
    window._close_shortcuts = []
    for sequence in ("Q", "Escape", "Ctrl+Q"):
        shortcut = QShortcut(QKeySequence(sequence), window)
        shortcut.activated.connect(window.close)
        window._close_shortcuts.append(shortcut)
    window._control_shortcuts = []
    shortcut_actions = (
        ("H", lambda: run_action(lambda: model.move_selection(-1))),
        ("L", lambda: run_action(lambda: model.move_selection(1))),
        ("Shift+H", lambda: run_action(lambda: model.move_selection(-1, small=True))),
        ("Shift+L", lambda: run_action(lambda: model.move_selection(1, small=True))),
        ("Left", lambda: run_action(lambda: model.move_selection(-1))),
        ("Right", lambda: run_action(lambda: model.move_selection(1))),
        ("Shift+Left", lambda: run_action(lambda: model.move_selection(-1, small=True))),
        ("Shift+Right", lambda: run_action(lambda: model.move_selection(1, small=True))),
        ("C", lambda: run_action(model.recenter)),
        ("+", lambda: run_action(lambda: model.zoom(1))),
        ("-", lambda: run_action(lambda: model.zoom(-1))),
        ("Return", lambda: run_action(model.tune_selected)),
        ("F", lambda: (frequency_entry.setFocus(), frequency_entry.selectAll())),
    )
    for sequence, action in shortcut_actions:
        shortcut = QShortcut(QKeySequence(sequence), window)
        shortcut.activated.connect(action)
        window._control_shortcuts.append(shortcut)

    timer = None
    if timeline is not None:
        timer = QTimer(window)

        def advance() -> None:
            if timeline.advance(model.publisher):
                update_display()
            else:
                timer.stop()
                update_display(ended=True)

        timer.timeout.connect(advance)
        timer.start(max(1, round(1000.0 / fps)))
        window._playback_timer = timer

    app.lastWindowClosed.connect(app.quit)
    window.show()
    display.setFocus()
    return app.exec()


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Fixture-first native KiwiSDR waterfall prototype")
    parser.add_argument("--fixture", type=Path, required=True)
    parser.add_argument("--rows", type=int, default=400)
    parser.add_argument("--repeat", type=int, default=1, help="repeat fixture frames to fill diagnostic history")
    parser.add_argument("--animate", action="store_true", help="publish fixture rows incrementally")
    parser.add_argument("--fps", type=float, default=20.0, help="animated fixture publication rate")
    parser.add_argument("--row-pixels", type=float, default=1.0, help="requested physical display pixels per W/F frame")
    parser.add_argument("--tuned-khz", type=float)
    parser.add_argument("--mode", default="am")
    parser.add_argument("--low-cut-hz", type=int, default=-5000)
    parser.add_argument("--high-cut-hz", type=int, default=5000)
    parser.add_argument("--main-step-hz", type=float, default=1000)
    parser.add_argument("--small-step-hz", type=float, default=100)
    parser.add_argument("--render-min-db", type=float, default=-100)
    parser.add_argument("--render-max-db", type=float, default=-40)
    parser.add_argument("--dry-run", action="store_true", help="build model and print summary without importing Qt")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)
    try:
        if args.fps <= 0:
            raise ValueError("GUI playback FPS must be positive")
        if args.row_pixels <= 0:
            raise ValueError("GUI row pixels must be positive")
        model = WaterfallGuiModel(
            history_rows=args.rows,
            render_min_db=args.render_min_db,
            render_max_db=args.render_max_db,
            tuned_khz=args.tuned_khz,
            mode=args.mode,
            low_cut_hz=args.low_cut_hz,
            high_cut_hz=args.high_cut_hz,
            main_step_hz=args.main_step_hz,
            small_step_hz=args.small_step_hz,
        )
        timeline = FixtureWaterfallTimeline.from_fixture(args.fixture, repeat=args.repeat)
        if args.animate:
            if args.dry_run:
                while timeline.advance(model.publisher):
                    model.image()
            else:
                return show_pyside_window(model, timeline=timeline, fps=args.fps, row_pixels=args.row_pixels)
        else:
            while timeline.advance(model.publisher):
                pass
        if args.dry_run:
            print(json.dumps(model.summary(
                animated=args.animate,
                requested_fps=args.fps if args.animate else None,
                requested_row_pixels=args.row_pixels,
            ), indent=2, sort_keys=True))
            return 0
        return show_pyside_window(model, row_pixels=args.row_pixels)
    except (OSError, RuntimeError, ValueError) as exc:
        raise SystemExit(f"kiwi-gui: error: {exc}") from exc


if __name__ == "__main__":
    raise SystemExit(main())
