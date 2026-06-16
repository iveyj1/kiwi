#!/usr/bin/env python3
"""Test-rig helper: render W/F JSONL fixtures as static matplotlib images.

This is intentionally outside the production package/console scripts. It is an
offline diagnostic for captured or synthetic fixtures.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Sequence

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = REPO_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from kiwi_client.fixtures import load_jsonl_events
from kiwi_client.waterfall import parse_waterfall_uncompressed


def load_waterfall_dbm_rows(path: Path, *, calibration_db: int = 0) -> list[list[int]]:
    """Load W/F binary events from a fixture as rows of calibrated-ish dBm values."""
    rows: list[list[int]] = []
    for event in load_jsonl_events(path):
        if event.dir != "rx" or event.stream != "wf" or event.type != "binary":
            continue
        frame = parse_waterfall_uncompressed(event.binary_payload)
        rows.append([value + calibration_db for value in frame.dbm])
    return rows


def matrix_shape(rows: Sequence[Sequence[int]]) -> tuple[int, int]:
    """Return matrix shape, requiring rectangular rows."""
    if not rows:
        return (0, 0)
    width = len(rows[0])
    if any(len(row) != width for row in rows):
        raise ValueError("waterfall rows are not rectangular")
    return (len(rows), width)


def render_waterfall_png(
    rows: Sequence[Sequence[int]],
    output: Path,
    *,
    min_dbm: int = -110,
    max_dbm: int = 0,
    cmap: str = "viridis",
    title: str | None = None,
) -> None:
    """Render a dBm row matrix to a PNG file using optional matplotlib."""
    height, width = matrix_shape(rows)
    if height == 0 or width == 0:
        raise ValueError("no W/F rows to render")
    try:
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError as exc:  # pragma: no cover - depends on optional local env
        raise RuntimeError("matplotlib is required for PNG rendering: pip install matplotlib") from exc

    output.parent.mkdir(parents=True, exist_ok=True)
    fig_width = max(8.0, min(18.0, width / 96.0))
    fig_height = max(2.0, min(10.0, height / 8.0 + 1.5))
    fig, ax = plt.subplots(figsize=(fig_width, fig_height), constrained_layout=True)
    image = ax.imshow(rows, aspect="auto", interpolation="nearest", origin="upper", vmin=min_dbm, vmax=max_dbm, cmap=cmap)
    ax.set_xlabel("W/F bin")
    ax.set_ylabel("Frame")
    if title:
        ax.set_title(title)
    fig.colorbar(image, ax=ax, label="dBm")
    fig.savefig(output, dpi=120)
    plt.close(fig)


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Test-rig renderer for static KiwiSDR W/F fixture images")
    parser.add_argument("fixture", type=Path, help="W/F JSONL fixture")
    parser.add_argument("output", type=Path, help="PNG output path")
    parser.add_argument("--min-db", type=int, default=-110, help="minimum dBm color scale")
    parser.add_argument("--max-db", type=int, default=0, help="maximum dBm color scale")
    parser.add_argument("--cal-db", type=int, default=0, help="calibration offset added to each dBm value")
    parser.add_argument("--cmap", default="viridis", help="matplotlib colormap name")
    parser.add_argument("--title", help="optional image title")
    parser.add_argument("--summary", action="store_true", help="print matrix shape before rendering")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_arg_parser()
    args = parser.parse_args(argv)
    if args.max_db <= args.min_db:
        parser.error("--max-db must be greater than --min-db")
    rows = load_waterfall_dbm_rows(args.fixture, calibration_db=args.cal_db)
    height, width = matrix_shape(rows)
    if args.summary:
        print(f"rows={height} bins={width} fixture={args.fixture}")
    try:
        render_waterfall_png(rows, args.output, min_dbm=args.min_db, max_dbm=args.max_db, cmap=args.cmap, title=args.title)
    except (RuntimeError, ValueError) as exc:
        parser.error(str(exc))
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
