"""Fixture-first native PySide6 waterfall prototype."""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path

from kiwi_client.fixtures import load_jsonl_events
from kiwi_client.protocol import parse_msg
from kiwi_client.waterfall import (
    WaterfallReceiverState,
    contextualize_waterfall_frame,
    parse_waterfall_uncompressed,
)
from kiwi_client.waterfall_raster import RasterImage, render_dbm_rows
from kiwi_client.waterfall_snapshots import WaterfallSnapshotPublisher


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

    def load_fixture(self, path: Path, *, repeat: int = 1) -> int:
        if repeat <= 0:
            raise ValueError("fixture repeat must be positive")
        events = load_jsonl_events(path)
        frames = 0
        for _ in range(repeat):
            state = WaterfallReceiverState()
            for event in events:
                if event.dir != "rx" or event.stream != "wf":
                    continue
                if event.type == "msg":
                    state = state.apply_msg_params(parse_msg(event.raw["text"]).params)
                elif event.type == "binary":
                    frame = contextualize_waterfall_frame(
                        parse_waterfall_uncompressed(event.binary_payload),
                        state,
                    )
                    self.publisher.append(frame)
                    frames += 1
        return frames

    def image(self) -> RasterImage:
        snapshot = self.publisher.latest()
        if snapshot is None:
            raise ValueError("waterfall GUI model has no frames")
        rows = tuple(row.dbm for row in snapshot.rows)
        if len(rows) < snapshot.max_rows:
            padding = tuple((-255,) * snapshot.width for _ in range(snapshot.max_rows - len(rows)))
            rows = padding + rows
        return render_dbm_rows(rows, min_dbm=self.render_min_db, max_dbm=self.render_max_db)

    def frequency_text(self) -> str:
        snapshot = self.publisher.latest()
        if snapshot is None or snapshot.current_start_khz is None or snapshot.current_span_khz is None:
            return "Frequency mapping unavailable"
        end_khz = snapshot.current_start_khz + snapshot.current_span_khz
        return f"{snapshot.current_start_khz:.4f} .. {end_khz:.4f} kHz"

    def status_text(self) -> str:
        snapshot = self.publisher.latest()
        if snapshot is None:
            return "0 frames"
        return f"{snapshot.generation} frames | {snapshot.width} bins | history {snapshot.max_rows} rows"

    def summary(self) -> dict:
        image = self.image()
        snapshot = self.publisher.latest()
        return {
            "backend": "PySide6",
            "frames": 0 if snapshot is None else snapshot.generation,
            "image_width": image.width,
            "image_height": image.height,
            "frequency": self.frequency_text(),
            "status": self.status_text(),
        }


def show_pyside_window(model: WaterfallGuiModel) -> int:
    """Display one direct-RGB fixture image, importing Qt only when requested."""
    try:
        from PySide6.QtCore import Qt
        from PySide6.QtGui import QImage, QPixmap
        from PySide6.QtWidgets import QApplication, QLabel, QMainWindow, QVBoxLayout, QWidget
    except ImportError as exc:
        raise RuntimeError("native GUI requires: pip install -e '.[gui-pyside]'") from exc

    image = model.image()
    app = QApplication.instance() or QApplication([])
    window = QMainWindow()
    window.setWindowTitle("KiwiSDR Waterfall Prototype")
    central = QWidget()
    layout = QVBoxLayout(central)
    frequency = QLabel(model.frequency_text())
    frequency.setAlignment(Qt.AlignmentFlag.AlignCenter)
    display = QLabel()
    display.setMinimumSize(640, 200)
    display.setScaledContents(True)
    status = QLabel(model.status_text())
    status.setAlignment(Qt.AlignmentFlag.AlignCenter)
    qimage = QImage(
        image.rgb,
        image.width,
        image.height,
        image.width * 3,
        QImage.Format.Format_RGB888,
    )
    display.setPixmap(QPixmap.fromImage(qimage))
    layout.addWidget(frequency)
    layout.addWidget(display, 1)
    layout.addWidget(status)
    window.setCentralWidget(central)
    window.resize(1200, 600)
    window.show()
    return app.exec()


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Fixture-first native KiwiSDR waterfall prototype")
    parser.add_argument("--fixture", type=Path, required=True)
    parser.add_argument("--rows", type=int, default=400)
    parser.add_argument("--repeat", type=int, default=1, help="repeat fixture frames to fill diagnostic history")
    parser.add_argument("--render-min-db", type=float, default=-100)
    parser.add_argument("--render-max-db", type=float, default=-40)
    parser.add_argument("--dry-run", action="store_true", help="build model and print summary without importing Qt")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)
    try:
        model = WaterfallGuiModel(
            history_rows=args.rows,
            render_min_db=args.render_min_db,
            render_max_db=args.render_max_db,
        )
        frames = model.load_fixture(args.fixture, repeat=args.repeat)
        if frames == 0:
            raise ValueError(f"fixture contains no W/F frames: {args.fixture}")
        if args.dry_run:
            print(json.dumps(model.summary(), indent=2, sort_keys=True))
            return 0
        return show_pyside_window(model)
    except (OSError, RuntimeError, ValueError) as exc:
        raise SystemExit(f"kiwi-gui: error: {exc}") from exc


if __name__ == "__main__":
    raise SystemExit(main())
