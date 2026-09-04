"""Fixture-first native PySide6 waterfall prototype."""

from __future__ import annotations

import argparse
import json
from collections import deque
from dataclasses import dataclass
from pathlib import Path

from kiwi_client.fixtures import load_jsonl_events
from kiwi_client.protocol import parse_msg
from kiwi_client.waterfall import (
    WaterfallFrame,
    WaterfallReceiverState,
    contextualize_waterfall_frame,
    parse_waterfall_uncompressed,
)
from kiwi_client.waterfall_raster import RasterImage, render_dbm_rows
from kiwi_client.waterfall_snapshots import WaterfallSnapshot, WaterfallSnapshotPublisher


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

    def update(self, snapshot: WaterfallSnapshot) -> RasterImage:
        if snapshot.generation > self.presented_generation:
            delta = snapshot.generation - self.presented_generation
            rebuild = (
                self._width != snapshot.width
                or self._max_rows != snapshot.max_rows
                or delta > len(snapshot.rows)
                or not self._rgb_rows
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
                self._rgb_rows.append(rendered.rgb)
            self.presented_generation = snapshot.generation

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

    def __post_init__(self) -> None:
        if self.render_max_db <= self.render_min_db:
            raise ValueError("render_max_db must be greater than render_min_db")
        self.publisher = WaterfallSnapshotPublisher(max_rows=self.history_rows)
        self.rasterizer = SnapshotRasterizer(min_dbm=self.render_min_db, max_dbm=self.render_max_db)

    def load_fixture(self, path: Path, *, repeat: int = 1) -> int:
        timeline = FixtureWaterfallTimeline.from_fixture(path, repeat=repeat)
        while timeline.advance(self.publisher):
            pass
        return timeline.total_frames

    def image(self) -> RasterImage:
        snapshot = self.publisher.latest()
        if snapshot is None:
            raise ValueError("waterfall GUI model has no frames")
        return self.rasterizer.update(snapshot)

    def frequency_text(self) -> str:
        snapshot = self.publisher.latest()
        if snapshot is None or snapshot.current_start_khz is None or snapshot.current_span_khz is None:
            return "Frequency mapping unavailable"
        end_khz = snapshot.current_start_khz + snapshot.current_span_khz
        return f"{snapshot.current_start_khz:.4f} .. {end_khz:.4f} kHz"

    def status_text(self, *, requested_fps: float | None = None, ended: bool = False) -> str:
        snapshot = self.publisher.latest()
        if snapshot is None:
            return "source 0 | presented 0"
        parts = [
            f"source {snapshot.generation}",
            f"presented {self.rasterizer.presented_generation}",
            f"{snapshot.width} bins",
            f"history {snapshot.max_rows} rows",
        ]
        if requested_fps is not None:
            parts.append(f"requested {requested_fps:g} FPS")
        if ended:
            parts.append("ended")
        return " | ".join(parts)

    def summary(self, *, animated: bool = False, requested_fps: float | None = None) -> dict:
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
        }


def show_pyside_window(
    model: WaterfallGuiModel,
    *,
    timeline: FixtureWaterfallTimeline | None = None,
    fps: float = 20.0,
) -> int:
    """Display direct-RGB fixture history, optionally publishing it on a timer."""
    try:
        from PySide6.QtCore import Qt, QTimer
        from PySide6.QtGui import QImage, QKeySequence, QPixmap, QShortcut
        from PySide6.QtWidgets import QApplication, QLabel, QMainWindow, QVBoxLayout, QWidget
    except ImportError as exc:
        raise RuntimeError("native GUI requires: pip install -e '.[gui-pyside]'") from exc

    if fps <= 0:
        raise ValueError("GUI playback FPS must be positive")
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
    display.setMinimumSize(640, 200)
    display.setScaledContents(True)
    status = QLabel()
    status.setAlignment(Qt.AlignmentFlag.AlignCenter)

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
        status.setText(model.status_text(requested_fps=fps if timeline is not None else None, ended=ended))

    update_display()
    layout.addWidget(frequency)
    layout.addWidget(display, 1)
    layout.addWidget(status)
    window.setCentralWidget(central)
    window.resize(1200, 600)
    window._close_shortcuts = []
    for sequence in ("Q", "Escape", "Ctrl+Q"):
        shortcut = QShortcut(QKeySequence(sequence), window)
        shortcut.activated.connect(window.close)
        window._close_shortcuts.append(shortcut)

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
    return app.exec()


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Fixture-first native KiwiSDR waterfall prototype")
    parser.add_argument("--fixture", type=Path, required=True)
    parser.add_argument("--rows", type=int, default=400)
    parser.add_argument("--repeat", type=int, default=1, help="repeat fixture frames to fill diagnostic history")
    parser.add_argument("--animate", action="store_true", help="publish fixture rows incrementally")
    parser.add_argument("--fps", type=float, default=20.0, help="animated fixture publication rate")
    parser.add_argument("--render-min-db", type=float, default=-100)
    parser.add_argument("--render-max-db", type=float, default=-40)
    parser.add_argument("--dry-run", action="store_true", help="build model and print summary without importing Qt")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)
    try:
        if args.fps <= 0:
            raise ValueError("GUI playback FPS must be positive")
        model = WaterfallGuiModel(
            history_rows=args.rows,
            render_min_db=args.render_min_db,
            render_max_db=args.render_max_db,
        )
        timeline = FixtureWaterfallTimeline.from_fixture(args.fixture, repeat=args.repeat)
        if args.animate:
            if args.dry_run:
                while timeline.advance(model.publisher):
                    model.image()
            else:
                return show_pyside_window(model, timeline=timeline, fps=args.fps)
        else:
            while timeline.advance(model.publisher):
                pass
        if args.dry_run:
            print(json.dumps(model.summary(animated=args.animate, requested_fps=args.fps if args.animate else None), indent=2, sort_keys=True))
            return 0
        return show_pyside_window(model)
    except (OSError, RuntimeError, ValueError) as exc:
        raise SystemExit(f"kiwi-gui: error: {exc}") from exc


if __name__ == "__main__":
    raise SystemExit(main())
