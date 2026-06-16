"""Offline fixture-to-text waterfall preview."""

from __future__ import annotations

import argparse
from pathlib import Path

from kiwi_client.fixtures import load_jsonl_events
from kiwi_client.waterfall import parse_waterfall_uncompressed
from kiwi_client.waterfall_render import DEFAULT_ASCII_RAMP, render_ascii_waterfall_row


def preview_waterfall_fixture(
    path: Path,
    *,
    min_dbm: int | float = -110,
    max_dbm: int | float = 0,
    ramp: str = DEFAULT_ASCII_RAMP,
) -> str:
    """Render W/F binary events in a JSONL fixture as ASCII rows."""
    rows: list[str] = []
    for event in load_jsonl_events(path):
        if event.dir != "rx" or event.stream != "wf" or event.type != "binary":
            continue
        frame = parse_waterfall_uncompressed(event.binary_payload)
        rows.append(render_ascii_waterfall_row(frame, min_dbm=min_dbm, max_dbm=max_dbm, ramp=ramp))
    return "\n".join(rows) + ("\n" if rows else "")


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Render a KiwiSDR W/F JSONL fixture as ASCII waterfall rows")
    parser.add_argument("fixture", type=Path, help="JSONL fixture containing W/F binary events")
    parser.add_argument("--min-db", type=float, default=-110.0, help="minimum dBm for fixed-scale rendering")
    parser.add_argument("--max-db", type=float, default=0.0, help="maximum dBm for fixed-scale rendering")
    parser.add_argument("--ramp", default=DEFAULT_ASCII_RAMP, help="ASCII ramp from low to high intensity")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_arg_parser()
    args = parser.parse_args(argv)
    if args.max_db <= args.min_db:
        parser.error("--max-db must be greater than --min-db")
    if len(args.ramp) < 2:
        parser.error("--ramp must contain at least two characters")
    print(preview_waterfall_fixture(args.fixture, min_dbm=args.min_db, max_dbm=args.max_db, ramp=args.ramp), end="")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
