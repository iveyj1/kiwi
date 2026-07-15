"""Standalone guarded live W/F ASCII preview."""

from __future__ import annotations

import argparse
import asyncio
import json
import tempfile
from pathlib import Path
from typing import Any, Callable

from kiwi_client.live_capture import LiveCaptureError
from kiwi_client.live_waterfall import LiveWaterfallCaptureConfig, capture_live_waterfall


def preview_live_waterfall(
    config: LiveWaterfallCaptureConfig,
    *,
    allow_live: bool = False,
    websocket_connect: Callable[..., Any] | None = None,
    row_callback: Callable[[str], None] | None = None,
) -> Path:
    """Run guarded W/F capture and emit ASCII rows as they arrive."""

    def on_status(metrics: dict) -> None:
        row = metrics.get("ascii_row")
        if isinstance(row, str) and row_callback is not None:
            row_callback(row)

    return asyncio.run(
        capture_live_waterfall(
            config,
            allow_live=allow_live,
            status_callback=on_status,
            websocket_connect=websocket_connect,
        )
    )


def _websocket_connect_for_main() -> Callable[..., Any] | None:
    """Return default websocket connector; isolated for harness monkeypatching."""
    return None


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Guarded short local KiwiSDR W/F ASCII preview")
    parser.add_argument("--host", default="10.0.0.40")
    parser.add_argument("--port", type=int, default=8073)
    parser.add_argument("--center-khz", type=float, default=5000.0)
    parser.add_argument("--zoom", type=int, default=0)
    parser.add_argument("--max-db", type=int, default=0, help="receiver waterfall max dB setting")
    parser.add_argument("--min-db", type=int, default=-110, help="receiver waterfall min dB setting")
    parser.add_argument("--render-max-db", type=int, help="local ASCII render max dB; defaults to --max-db")
    parser.add_argument("--render-min-db", type=int, help="local ASCII render min dB; defaults to --min-db")
    parser.add_argument("--ramp", default=" .:-=+*#%@", help="ASCII intensity ramp from dim to bright")
    parser.add_argument("--speed", type=int, default=1)
    parser.add_argument("--interp", type=int, default=13)
    parser.add_argument("--duration-seconds", type=float, default=60.0)
    parser.add_argument("--max-frames", type=int, default=50)
    parser.add_argument("--timestamp", type=int)
    parser.add_argument("--save-fixture", type=Path, help="optional JSONL fixture output path")
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--allow-live", action="store_true")
    parser.add_argument("--json", action="store_true", help="print dry-run plan as JSON; live preview always prints rows")
    return parser


def config_from_args(args: argparse.Namespace, output: Path) -> LiveWaterfallCaptureConfig:
    return LiveWaterfallCaptureConfig(
        host=args.host,
        port=args.port,
        output=output,
        center_khz=args.center_khz,
        zoom=args.zoom,
        maxdb=args.max_db,
        mindb=args.min_db,
        render_maxdb=args.render_max_db,
        render_mindb=args.render_min_db,
        ascii_ramp=args.ramp,
        speed=args.speed,
        interp=args.interp,
        duration_seconds=args.duration_seconds,
        max_frames=args.max_frames,
        timestamp=args.timestamp,
        overwrite=args.overwrite,
    )


def _run_live_preview(args: argparse.Namespace, output: Path) -> int:
    config = config_from_args(args, output)
    config.validate()
    if not args.allow_live:
        raise LiveCaptureError("live waterfall preview requires --allow-live; use --dry-run for a plan")
    preview_live_waterfall(
        config,
        allow_live=True,
        websocket_connect=_websocket_connect_for_main(),
        row_callback=print,
    )
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = build_arg_parser()
    args = parser.parse_args(argv)
    if args.dry_run:
        output = args.save_fixture or Path("<temporary-wf-preview.jsonl>")
        config = config_from_args(args, output)
        try:
            config.validate()
        except LiveCaptureError as exc:
            parser.error(str(exc))
        print(json.dumps(config.dry_run_plan(), indent=2, sort_keys=True))
        return 0

    try:
        if args.save_fixture is not None:
            return _run_live_preview(args, args.save_fixture)
        with tempfile.TemporaryDirectory(prefix="kiwi-wf-preview-") as directory:
            return _run_live_preview(args, Path(directory) / "preview.jsonl")
    except LiveCaptureError as exc:
        parser.error(str(exc))
    return 2


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
