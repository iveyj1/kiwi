#!/usr/bin/env python3
"""Toolkit-independent synthetic workload for waterfall GUI benchmarks."""

from __future__ import annotations

import argparse
import json
import statistics
import time
from dataclasses import asdict, dataclass

from kiwi_client.waterfall import WaterfallFrame
from kiwi_client.waterfall_snapshots import WaterfallSnapshotPublisher


@dataclass(frozen=True)
class BenchmarkResult:
    width: int
    history_rows: int
    source_fps: float
    consumer_fps: float
    produced_frames: int
    presented_snapshots: int
    coalesced_generations: int
    virtual_duration_seconds: float
    elapsed_seconds: float
    producer_fps: float
    mean_publish_ms: float
    p95_publish_ms: float


def synthetic_frame(index: int, *, width: int) -> WaterfallFrame:
    """Return a deterministic changing 1024-style W/F row."""
    dbm = tuple(-110 + ((column * 7 + index * 3) % 70) for column in range(width))
    return WaterfallFrame(
        sequence=index,
        bins=tuple(value + 255 for value in dbm),
        dbm=dbm,
        start_khz=4882.8125,
        center_khz=5000.0,
        span_khz=234.375,
        bin_width_hz=234_375.0 / width,
        flags_x_zoom_server=7,
    )


def run_no_window_baseline(
    *,
    width: int = 1024,
    history_rows: int = 400,
    frames: int = 1200,
    source_fps: float = 20.0,
    consumer_fps: float = 20.0,
) -> BenchmarkResult:
    """Publish deterministic frames and sample latest snapshots at a virtual rate."""
    if width <= 0 or history_rows <= 0 or frames <= 0:
        raise ValueError("width, history_rows and frames must be positive")
    if source_fps <= 0 or consumer_fps <= 0:
        raise ValueError("source_fps and consumer_fps must be positive")

    publisher = WaterfallSnapshotPublisher(max_rows=history_rows)
    consume_budget = 0.0
    presented = 0
    coalesced = 0
    last_generation = 0
    publish_times: list[float] = []
    started = time.perf_counter()

    for index in range(1, frames + 1):
        publish_started = time.perf_counter()
        publisher.append(synthetic_frame(index, width=width))
        publish_times.append(time.perf_counter() - publish_started)
        consume_budget += consumer_fps / source_fps
        if consume_budget >= 1.0:
            snapshot = publisher.wait_for_newer(last_generation, timeout=0)
            if snapshot is not None:
                coalesced += max(0, snapshot.generation - last_generation - 1)
                last_generation = snapshot.generation
                presented += 1
            consume_budget %= 1.0

    elapsed = time.perf_counter() - started
    sorted_times = sorted(publish_times)
    p95_index = min(len(sorted_times) - 1, max(0, int(len(sorted_times) * 0.95) - 1))
    return BenchmarkResult(
        width=width,
        history_rows=history_rows,
        source_fps=source_fps,
        consumer_fps=consumer_fps,
        produced_frames=frames,
        presented_snapshots=presented,
        coalesced_generations=coalesced,
        virtual_duration_seconds=frames / source_fps,
        elapsed_seconds=elapsed,
        producer_fps=frames / elapsed if elapsed else float("inf"),
        mean_publish_ms=statistics.fmean(publish_times) * 1000.0,
        p95_publish_ms=sorted_times[p95_index] * 1000.0,
    )


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="No-window waterfall snapshot benchmark")
    parser.add_argument("--history-rows", default="200,400,800", help="comma-separated history depths")
    parser.add_argument("--width", type=int, default=1024)
    parser.add_argument("--frames", type=int, default=1200)
    parser.add_argument("--source-fps", type=float, default=20.0)
    parser.add_argument("--consumer-fps", type=float, default=20.0)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)
    rows = [int(value) for value in args.history_rows.split(",")]
    for history_rows in rows:
        result = run_no_window_baseline(
            width=args.width,
            history_rows=history_rows,
            frames=args.frames,
            source_fps=args.source_fps,
            consumer_fps=args.consumer_fps,
        )
        print(json.dumps(asdict(result), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
