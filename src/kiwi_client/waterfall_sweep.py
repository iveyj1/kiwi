"""Measure the W/F bin center offset by sweeping the window past a known tone.

The bin center offset is currently a fitted constant bounded only to
`0.762 < offset <= 0.895` by AM broadcast carriers, whose own frequency
tolerance of +/-20 Hz limits how well any single carrier can pin it down.

This module measures it directly instead. Against a reference of known exact
frequency (WWVB at 60 kHz, WWV, or the receiver's own signal generator), the
window is stepped past the tone in small increments. Each window position gives
one constraint on the offset, and the intersection of those constraints narrows
as the sweep crosses a bin boundary.

Precision is set by the step size rather than by the reference's frequency
error, so it is limited by `2**(zoom_max - zoom)` window positions per bin: 32
at zoom 9, giving about +/-0.016 bins.

Pure analysis lives at the top of this module and is testable without a
receiver. The guarded live sweep and CLI follow.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import math
import time
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Iterable, Sequence
from zoneinfo import ZoneInfo

from kiwi_client.capture import JsonlCaptureWriter, WaterfallCaptureMetadata
from kiwi_client.commands import encode_auth, encode_keepalive
from kiwi_client.live_capture import (
    LiveCaptureError,
    allowed_receiver_names,
    keepalive_due,
    raise_for_kiwi_error,
)
from kiwi_client.protocol import parse_msg
from kiwi_client.waterfall import (
    WaterfallFrame,
    WaterfallSessionMetadata,
    WaterfallSpan,
    parse_waterfall_uncompressed,
)

WEBSOCKET_CLOSE_TIMEOUT_SECONDS = 0.25
DEFAULT_MIN_SNR_DB = 6.0
DEFAULT_PEAK_SEARCH_RADIUS = 4
# Shared by the dataclass and the CLI so the two cannot drift apart.
DEFAULT_REFERENCE_KHZ = 60.0
DEFAULT_ZOOM = 9
DEFAULT_STEPS = 40
DEFAULT_STEP_HZ = 2.0
DEFAULT_FRAMES_PER_STEP = 20
DEFAULT_DURATION_SECONDS = 120.0


def average_dbm(frames: Sequence[WaterfallFrame]) -> tuple[float, ...]:
    """Return the per-bin mean across frames.

    Averaging rather than max-hold matters when the reference is near the noise
    floor: a stable carrier survives averaging while noise averages down, and
    max-hold would latch onto noise peaks and bias the measurement.
    """
    if not frames:
        raise ValueError("cannot average an empty frame sequence")
    width = len(frames[0].dbm)
    if any(len(frame.dbm) != width for frame in frames):
        raise ValueError("frames have inconsistent bin counts")
    count = len(frames)
    return tuple(sum(frame.dbm[i] for frame in frames) / count for i in range(width))


def noise_floor_dbm(values: Sequence[float]) -> float:
    """Return the median bin level, used as a robust noise-floor estimate."""
    if not values:
        raise ValueError("cannot estimate a noise floor from no bins")
    ordered = sorted(values)
    middle = len(ordered) // 2
    if len(ordered) % 2:
        return ordered[middle]
    return (ordered[middle - 1] + ordered[middle]) / 2


def find_peak_bin(values: Sequence[float], center: int, radius: int = DEFAULT_PEAK_SEARCH_RADIUS) -> int:
    """Return the index of the largest value within `radius` bins of `center`."""
    if not values:
        raise ValueError("cannot find a peak in no bins")
    low = max(0, center - radius)
    high = min(len(values) - 1, center + radius)
    if low > high:
        raise ValueError(f"peak search window falls outside the frame: center={center}")
    return max(range(low, high + 1), key=lambda i: values[i])


def group_frames_by_window(frames: Iterable[WaterfallFrame]) -> dict[int, list[WaterfallFrame]]:
    """Group frames by `x_bin_server`, which identifies the tuned window exactly.

    Grouping on what the receiver reports avoids having to correlate frames with
    the retune commands that produced them, and tolerates the receiver
    quantising a requested `cf` to its own grid.
    """
    grouped: dict[int, list[WaterfallFrame]] = defaultdict(list)
    for frame in frames:
        if frame.x_bin_server is None:
            raise ValueError("frame has no x_bin_server; cannot identify its window")
        grouped[frame.x_bin_server].append(frame)
    return dict(grouped)


@dataclass(frozen=True)
class SweepSample:
    """One window position and the reference tone's measured peak within it."""

    x_bin_server: int
    frame_count: int
    peak_bin: int
    peak_dbm: float
    floor_dbm: float

    @property
    def snr_db(self) -> float:
        """Return how far the peak stands above the median bin level."""
        return self.peak_dbm - self.floor_dbm


def sample_window(
    x_bin_server: int,
    frames: Sequence[WaterfallFrame],
    *,
    span: WaterfallSpan,
    reference_hz: float,
    search_radius: int = DEFAULT_PEAK_SEARCH_RADIUS,
) -> SweepSample:
    """Reduce one window's frames to a single peak measurement."""
    averaged = average_dbm(frames)
    naive = (reference_hz - span.start_hz(x_bin_server)) / span.bin_width_hz
    peak = find_peak_bin(averaged, round(naive), search_radius)
    return SweepSample(
        x_bin_server=x_bin_server,
        frame_count=len(frames),
        peak_bin=peak,
        peak_dbm=averaged[peak],
        floor_dbm=noise_floor_dbm(averaged),
    )


@dataclass(frozen=True)
class SweepResult:
    """Offset constraints accumulated across every window position in a sweep."""

    reference_hz: float
    span: WaterfallSpan
    samples: tuple[SweepSample, ...]

    def usable(self, min_snr_db: float = DEFAULT_MIN_SNR_DB) -> tuple[SweepSample, ...]:
        """Return only samples whose peak stands clearly above the noise floor."""
        return tuple(sample for sample in self.samples if sample.snr_db >= min_snr_db)

    def naive_index(self, sample: SweepSample) -> float:
        """Return where the mapping predicts the reference lands, before any offset."""
        return (self.reference_hz - self.span.start_hz(sample.x_bin_server)) / self.span.bin_width_hz

    def offset_window(self, min_snr_db: float = DEFAULT_MIN_SNR_DB) -> tuple[float, float]:
        """Return `(low, high)` bounding the offset, as `low < offset <= high`.

        Each sample requires `round(naive - offset) == peak_bin`, which admits
        offsets in `(naive - peak - 0.5, naive - peak + 0.5]`. The sweep's answer
        is the intersection, which narrows sharply once the peak changes bin.
        """
        usable = self.usable(min_snr_db)
        if not usable:
            raise ValueError(f"no sweep sample reached {min_snr_db} dB SNR; the reference was not detected")
        low = -math.inf
        high = math.inf
        for sample in usable:
            offset = self.naive_index(sample) - sample.peak_bin
            low = max(low, offset - 0.5)
            high = min(high, offset + 0.5)
        if low >= high:
            raise ValueError(
                "sweep samples give contradictory offsets, so no single constant fits them "
                f"(window {low:.3f}..{high:.3f}). The offset is known not to be constant across "
                "window positions on at least one local receiver; see bin_transitions() and "
                "docs/kiwi-protocol.md. Other causes are a mis-specified reference or a peak "
                "lost in noise."
            )
        return (low, high)

    def bin_transitions(self, min_snr_db: float = DEFAULT_MIN_SNR_DB) -> tuple[tuple[int, int, int], ...]:
        """Return `(x_bin_server, from_bin, to_bin)` for each peak bin change.

        Under a constant offset these are spaced by exactly one bin, that is
        `2**(zoom_max - zoom)` window positions. Spacing that differs from that
        is direct evidence the offset varies with window position.
        """
        usable = self.usable(min_snr_db)
        transitions = []
        for previous, current in zip(usable, usable[1:]):
            if current.peak_bin != previous.peak_bin:
                transitions.append((current.x_bin_server, previous.peak_bin, current.peak_bin))
        return tuple(transitions)

    def positions_per_bin(self) -> float:
        """Return how many window positions the model puts in one bin."""
        return self.span.bin_width_hz / self.span.unit_hz

    def observed_positions_per_bin(self, min_snr_db: float = DEFAULT_MIN_SNR_DB) -> float | None:
        """Return the measured spacing between peak bin transitions, or None.

        Requires at least two transitions. Disagreement with
        `positions_per_bin()` means a constant offset cannot describe the data.
        """
        transitions = self.bin_transitions(min_snr_db)
        if len(transitions) < 2:
            return None
        spans = [b[0] - a[0] for a, b in zip(transitions, transitions[1:])]
        return sum(spans) / len(spans)

    def offset_statistics(self, min_snr_db: float = DEFAULT_MIN_SNR_DB) -> dict[str, float]:
        """Return per-position offset statistics, valid whether or not a constant fits."""
        usable = self.usable(min_snr_db)
        if not usable:
            raise ValueError(f"no sweep sample reached {min_snr_db} dB SNR; the reference was not detected")
        offsets = [self.naive_index(sample) - sample.peak_bin for sample in usable]
        ordered = sorted(offsets)
        return {
            "count": float(len(offsets)),
            "mean": sum(offsets) / len(offsets),
            "min": ordered[0],
            "max": ordered[-1],
            "range": ordered[-1] - ordered[0],
        }

    def crossed_bin_boundary(self, min_snr_db: float = DEFAULT_MIN_SNR_DB) -> bool:
        """Return whether the peak changed bin during the sweep.

        Without a crossing the window is only as narrow as one sample allows,
        about one bin, and the sweep has not improved on a single measurement.
        """
        return len({sample.peak_bin for sample in self.usable(min_snr_db)}) > 1

    def summary(self, min_snr_db: float = DEFAULT_MIN_SNR_DB) -> dict[str, Any]:
        """Return a JSON-serialisable summary of what the sweep established.

        A sweep whose samples admit no single constant offset still summarises,
        reporting `constant_offset_fits: false` plus the statistics and
        transition spacing that describe the failure. Only a sweep that detected
        nothing at all raises.
        """
        usable = self.usable(min_snr_db)
        statistics = self.offset_statistics(min_snr_db)
        observed = self.observed_positions_per_bin(min_snr_db)
        payload: dict[str, Any] = {
            "reference_hz": self.reference_hz,
            "zoom": self.span.zoom,
            "bin_width_hz": self.span.bin_width_hz,
            "window_positions": len(self.samples),
            "usable_positions": len(usable),
            "crossed_bin_boundary": self.crossed_bin_boundary(min_snr_db),
            "best_snr_db": max((sample.snr_db for sample in usable), default=0.0),
            "offset_mean": statistics["mean"],
            "offset_min": statistics["min"],
            "offset_max": statistics["max"],
            "offset_range": statistics["range"],
            "model_positions_per_bin": self.positions_per_bin(),
            "observed_positions_per_bin": observed,
            "bin_transitions": [list(item) for item in self.bin_transitions(min_snr_db)],
        }
        try:
            low, high = self.offset_window(min_snr_db)
        except ValueError:
            payload["constant_offset_fits"] = False
            return payload
        payload.update(
            {
                "constant_offset_fits": True,
                "offset_low": low,
                "offset_high": high,
                "offset_center": (low + high) / 2,
                "offset_width_bins": high - low,
                "offset_width_hz": (high - low) * self.span.bin_width_hz,
            }
        )
        return payload


@dataclass(frozen=True)
class WaterfallSweepConfig:
    """Configuration for one guarded window sweep past a known reference tone."""

    host: str
    port: int
    output: Path
    reference_khz: float = DEFAULT_REFERENCE_KHZ
    zoom: int = DEFAULT_ZOOM
    steps: int = DEFAULT_STEPS
    step_hz: float = DEFAULT_STEP_HZ
    frames_per_step: int = DEFAULT_FRAMES_PER_STEP
    maxdb: int = 0
    mindb: int = -110
    speed: int = 4
    interp: int = 10
    min_snr_db: float = DEFAULT_MIN_SNR_DB
    duration_seconds: float = DEFAULT_DURATION_SECONDS
    timestamp: int | None = None
    overwrite: bool = False
    receivers_restricted: bool = True
    allowed_receivers: tuple[str, ...] | None = None

    @property
    def receiver(self) -> str:
        return f"{self.host}:{self.port}"

    def validate(self) -> None:
        """Validate guardrails and sweep geometry before any live operation."""
        if self.receivers_restricted and self.receiver not in allowed_receiver_names(self.allowed_receivers):
            raise LiveCaptureError(f"receiver must be one of the allowed receivers: {allowed_receiver_names(self.allowed_receivers)}")
        if self.reference_khz <= 0:
            raise LiveCaptureError("reference frequency must be positive")
        if self.zoom < 0:
            raise LiveCaptureError("zoom must be >= 0")
        if self.steps < 2:
            raise LiveCaptureError("a sweep needs at least 2 window positions")
        if self.step_hz <= 0:
            raise LiveCaptureError("step size must be positive")
        if self.frames_per_step < 1:
            raise LiveCaptureError("frames_per_step must be >= 1")
        if self.speed < 1 or self.speed > 4:
            raise LiveCaptureError("waterfall speed must be in range 1..4")
        if self.maxdb <= self.mindb:
            raise LiveCaptureError("maxdb must be greater than mindb")
        if self.duration_seconds <= 0:
            raise LiveCaptureError("sweep duration must be positive")
        if self.output.exists() and not self.overwrite:
            raise LiveCaptureError(f"output already exists; use --overwrite to replace: {self.output}")
        half_span_khz = 30_000.0 / 2**self.zoom / 2
        if half_span_khz > self.reference_khz:
            raise LiveCaptureError(
                f"zoom {self.zoom} spans +/-{half_span_khz:.2f} kHz, so {self.reference_khz} kHz cannot be centred; "
                f"use zoom {math.ceil(math.log2(15_000.0 / self.reference_khz))} or higher"
            )
        # A sweep that never crosses a bin boundary cannot beat a single
        # measurement, so reject that configuration rather than capturing a
        # fixture that turns out to say nothing.
        bin_hz = 30_000_000.0 / (1024 * 2**self.zoom)
        sweep_hz = self.steps * self.step_hz
        if sweep_hz < 1.2 * bin_hz:
            raise LiveCaptureError(
                f"sweep spans {sweep_hz:.1f} Hz but one bin is {bin_hz:.1f} Hz at zoom {self.zoom}; "
                f"it may never cross a bin boundary. Use at least "
                f"{math.ceil(1.2 * bin_hz / self.step_hz)} steps, or a larger --step-hz"
            )
        # Precision is the step size in bins; a step coarser than the existing
        # 0.133-bin bound would not improve on what the AM carriers already gave.
        step_bins = self.step_hz / bin_hz
        if step_bins > 0.1:
            raise LiveCaptureError(
                f"--step-hz {self.step_hz} is {step_bins:.3f} bins at zoom {self.zoom}, too coarse to improve "
                f"on the existing 0.133 bin bound; use --step-hz {0.05 * bin_hz:.2f} or smaller"
            )

    def center_khz_for_step(self, index: int) -> float:
        """Return the tuned centre for one sweep step.

        Steps walk the window past the reference. The receiver quantises `cf` to
        its own grid, which is fine: frames are grouped by the `x_bin_server`
        the receiver reports rather than by what was requested.
        """
        return self.reference_khz + (index - self.steps // 2) * self.step_hz / 1000.0

    def setup_commands(self, center_khz: float) -> list[str]:
        """Return the commands that tune one sweep step."""
        return [
            f"SET zoom={self.zoom} cf={center_khz:.4f}",
            f"SET maxdb={self.maxdb} mindb={self.mindb}",
            f"SET wf_speed={self.speed}",
            "SET wf_comp=0",
            f"SET interp={self.interp}",
        ]

    def websocket_uri(self) -> str:
        """Return the KiwiSDR W/F WebSocket URI for this sweep."""
        timestamp = self.timestamp if self.timestamp is not None else int(time.time())
        return f"ws://{self.host}:{self.port}/{timestamp}/W/F"

    def dry_run_plan(self) -> dict[str, Any]:
        """Return a JSON-serialisable plan without connecting."""
        span_khz = 30_000.0 / 2**self.zoom
        bin_hz = span_khz * 1000.0 / 1024
        unit_hz = 30_000_000.0 / (1024 * 2**14)
        return {
            "receiver": self.receiver,
            "websocket_uri": self.websocket_uri(),
            "output": str(self.output),
            "reference_khz": self.reference_khz,
            "zoom": self.zoom,
            "span_khz": span_khz,
            "bin_width_hz": bin_hz,
            "window_positions": self.steps,
            "step_hz": self.step_hz,
            "step_bins": self.step_hz / bin_hz,
            "positions_per_bin": bin_hz / unit_hz,
            "sweep_width_bins": self.steps * self.step_hz / bin_hz,
            "frames_per_step": self.frames_per_step,
            "total_frames": self.steps * self.frames_per_step,
            "min_snr_db": self.min_snr_db,
            "duration_seconds": self.duration_seconds,
            "center_khz_first": self.center_khz_for_step(0),
            "center_khz_last": self.center_khz_for_step(self.steps - 1),
            "commands_first_step": [encode_auth(), *self.setup_commands(self.center_khz_for_step(0))],
        }


def analyse_sweep_frames(
    frames: Sequence[WaterfallFrame],
    *,
    span: WaterfallSpan,
    reference_hz: float,
    search_radius: int = DEFAULT_PEAK_SEARCH_RADIUS,
) -> SweepResult:
    """Reduce captured sweep frames to per-window samples and offset constraints."""
    grouped = group_frames_by_window(frames)
    samples = tuple(
        sample_window(x_bin, window_frames, span=span, reference_hz=reference_hz, search_radius=search_radius)
        for x_bin, window_frames in sorted(grouped.items())
    )
    return SweepResult(reference_hz=reference_hz, span=span, samples=samples)


def load_sweep_fixture(path: Path, *, reference_khz: float) -> SweepResult:
    """Load a captured sweep fixture and analyse it without any network access."""
    from kiwi_client.fixtures import load_jsonl_events

    metadata = WaterfallSessionMetadata()
    frames: list[WaterfallFrame] = []
    for event in load_jsonl_events(path):
        if event.type == "msg":
            metadata.observe(parse_msg(event.raw["text"]).params)
        elif event.type == "binary":
            frames.append(parse_waterfall_uncompressed(event.binary_payload))
    span = metadata.span()
    if span is None:
        raise LiveCaptureError(f"fixture does not carry enough W/F geometry to analyse: {path}")
    if not frames:
        raise LiveCaptureError(f"fixture contains no W/F frames: {path}")
    return analyse_sweep_frames(frames, span=span, reference_hz=reference_khz * 1000.0)


def export_samples(result: SweepResult, path: Path, *, min_snr_db: float = DEFAULT_MIN_SNR_DB) -> Path:
    """Write a compact record of a sweep: geometry plus one row per window position.

    A raw sweep fixture runs to megabytes because it keeps every frame. This
    keeps only what the offset analysis consumes, so a result can be committed
    as evidence and re-examined later.
    """
    payload = {
        "reference_hz": result.reference_hz,
        "bandwidth_hz": result.span.bandwidth_hz,
        "zoom": result.span.zoom,
        "fft_size": result.span.fft_size,
        "zoom_max": result.span.zoom_max,
        "summary": result.summary(min_snr_db),
        "samples": [
            {
                "x_bin_server": s.x_bin_server,
                "frame_count": s.frame_count,
                "peak_bin": s.peak_bin,
                "peak_dbm": s.peak_dbm,
                "floor_dbm": s.floor_dbm,
            }
            for s in result.samples
        ],
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    return path


def load_exported_samples(path: Path) -> SweepResult:
    """Rebuild a `SweepResult` from a record written by `export_samples()`."""
    payload = json.loads(path.read_text())
    span = WaterfallSpan(
        bandwidth_hz=payload["bandwidth_hz"],
        zoom=payload["zoom"],
        fft_size=payload["fft_size"],
        zoom_max=payload["zoom_max"],
    )
    samples = tuple(
        SweepSample(
            x_bin_server=row["x_bin_server"],
            frame_count=row["frame_count"],
            peak_bin=row["peak_bin"],
            peak_dbm=row["peak_dbm"],
            floor_dbm=row["floor_dbm"],
        )
        for row in payload["samples"]
    )
    return SweepResult(reference_hz=payload["reference_hz"], span=span, samples=samples)


def _capture_metadata(config: WaterfallSweepConfig) -> WaterfallCaptureMetadata:
    return WaterfallCaptureMetadata(
        receiver=config.receiver,
        utc_time=datetime.now(tz=ZoneInfo("UTC")).isoformat(),
        local_time=datetime.now().astimezone().isoformat(),
        center_khz=config.reference_khz,
        zoom=config.zoom,
        maxdb=config.maxdb,
        mindb=config.mindb,
        speed=config.speed,
        compression=False,
        notes=f"W/F bin offset sweep past {config.reference_khz} kHz reference",
    )


async def sweep_waterfall_window(
    config: WaterfallSweepConfig,
    *,
    allow_live: bool = False,
    status_callback: Callable[[dict], None] | None = None,
    websocket_connect: Callable[..., Any] | None = None,
) -> Path:
    """Run one guarded window sweep and write a JSONL fixture."""
    config.validate()
    if not allow_live:
        raise LiveCaptureError("waterfall sweep requires allow_live=True")

    if websocket_connect is None:
        try:
            import websockets
        except ImportError as exc:
            raise LiveCaptureError("live sweep requires optional dependency: pip install '.[live]'") from exc
        websocket_connect = websockets.connect

    writer = JsonlCaptureWriter(_capture_metadata(config))
    start = time.monotonic()
    last_keepalive = start

    async with websocket_connect(
        config.websocket_uri(),
        max_queue=0,
        close_timeout=WEBSOCKET_CLOSE_TIMEOUT_SECONDS,
    ) as websocket:
        writer.add_tx_cmd(time.monotonic() - start, encode_auth(), stream="wf")
        await websocket.send(encode_auth())

        for step in range(config.steps):
            center = config.center_khz_for_step(step)
            for command in config.setup_commands(center):
                writer.add_tx_cmd(time.monotonic() - start, command, stream="wf")
                await websocket.send(command)

            collected = 0
            while collected < config.frames_per_step:
                elapsed = time.monotonic() - start
                if elapsed >= config.duration_seconds:
                    raise LiveCaptureError(
                        f"sweep exceeded {config.duration_seconds}s at step {step}/{config.steps}; "
                        "reduce --steps or --frames-per-step"
                    )
                now = time.monotonic()
                if keepalive_due(now, last_keepalive, sent_setup=True):
                    command = encode_keepalive()
                    writer.add_tx_cmd(now - start, command, stream="wf")
                    await websocket.send(command)
                    last_keepalive = now

                message = await asyncio.wait_for(
                    websocket.recv(), timeout=max(0.1, config.duration_seconds - elapsed)
                )
                t = time.monotonic() - start
                if isinstance(message, str):
                    writer.add_rx_msg(t, message, stream="wf")
                    raise_for_kiwi_error(parse_msg(message).params, receiver=config.receiver)
                    continue
                payload = bytes(message)
                if payload.startswith(b"MSG"):
                    text = payload.decode("utf-8", errors="replace")
                    writer.add_rx_msg(t, text, stream="wf")
                    raise_for_kiwi_error(parse_msg(text).params, receiver=config.receiver)
                    continue
                if not payload.startswith(b"W/F"):
                    continue

                writer.add_rx_binary(t, payload, stream="wf")
                collected += 1

            if status_callback is not None:
                status_callback({"step": step + 1, "steps": config.steps, "center_khz": center})

    writer.write(config.output)
    return config.output


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Measure the W/F bin center offset by sweeping the window past a known reference tone"
    )
    parser.add_argument("--host", default="10.0.0.40")
    parser.add_argument("--port", type=int, default=8073)
    parser.add_argument("--output", type=Path, help="JSONL fixture output path; required for a live sweep")
    parser.add_argument(
        "--analyse",
        type=Path,
        help="analyse an existing sweep fixture instead of capturing; no network access",
    )
    parser.add_argument(
        "--reference-khz",
        type=float,
        default=DEFAULT_REFERENCE_KHZ,
        help="exact frequency of the reference tone; 60 for WWVB, 10000 for WWV",
    )
    parser.add_argument("--zoom", type=int, default=DEFAULT_ZOOM)
    parser.add_argument("--steps", type=int, default=DEFAULT_STEPS, help="number of window positions")
    parser.add_argument("--step-hz", type=float, default=DEFAULT_STEP_HZ, help="centre frequency change per step")
    parser.add_argument("--frames-per-step", type=int, default=DEFAULT_FRAMES_PER_STEP, help="frames averaged at each position")
    parser.add_argument("--max-db", type=int, default=0)
    parser.add_argument("--min-db", type=int, default=-110)
    parser.add_argument("--speed", type=int, default=4)
    parser.add_argument("--interp", type=int, default=10)
    parser.add_argument("--min-snr-db", type=float, default=DEFAULT_MIN_SNR_DB)
    parser.add_argument("--duration-seconds", type=float, default=DEFAULT_DURATION_SECONDS)
    parser.add_argument("--timestamp", type=int)
    parser.add_argument(
        "--export-samples",
        type=Path,
        help="write a compact per-position record, small enough to commit as evidence",
    )
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--allow-live", action="store_true")
    parser.add_argument("--json", action="store_true")
    return parser


def config_from_args(args: argparse.Namespace) -> WaterfallSweepConfig:
    return WaterfallSweepConfig(
        host=args.host,
        port=args.port,
        output=args.output or Path("<no-output>"),
        reference_khz=args.reference_khz,
        zoom=args.zoom,
        steps=args.steps,
        step_hz=args.step_hz,
        frames_per_step=args.frames_per_step,
        maxdb=args.max_db,
        mindb=args.min_db,
        speed=args.speed,
        interp=args.interp,
        min_snr_db=args.min_snr_db,
        duration_seconds=args.duration_seconds,
        timestamp=args.timestamp,
        overwrite=args.overwrite,
    )


def format_sweep_report(result: SweepResult, min_snr_db: float) -> str:
    """Render a human-readable sweep report."""
    lines = [
        f"reference   {result.reference_hz / 1000:.4f} kHz",
        f"zoom        {result.span.zoom}  bin width {result.span.bin_width_hz:.4f} Hz",
        "",
        f"{'x_bin':>10} {'frames':>7} {'naive':>9} {'peak':>6} {'snr dB':>7}  {'offset':>7}",
    ]
    for sample in result.samples:
        naive = result.naive_index(sample)
        mark = " " if sample.snr_db >= min_snr_db else "*"
        lines.append(
            f"{sample.x_bin_server:>10} {sample.frame_count:>7} {naive:>9.3f} "
            f"{sample.peak_bin:>6} {sample.snr_db:>7.1f}{mark} {naive - sample.peak_bin:>+7.3f}"
        )
    usable = result.usable(min_snr_db)
    if len(usable) < len(result.samples):
        lines.append(f"  (* = below {min_snr_db} dB SNR, excluded)")
    lines.append("")
    statistics = result.offset_statistics(min_snr_db)
    model = result.positions_per_bin()
    observed = result.observed_positions_per_bin(min_snr_db)
    lines.append(
        f"offset mean {statistics['mean']:+.3f}  min {statistics['min']:+.3f}  "
        f"max {statistics['max']:+.3f}  range {statistics['range']:.3f} bins"
    )
    transitions = result.bin_transitions(min_snr_db)
    if transitions:
        spacing = [b[0] - a[0] for a, b in zip(transitions, transitions[1:])]
        lines.append(
            f"peak bin transitions at x_bin {[t[0] for t in transitions]}"
            + (f", spacing {spacing} positions" if spacing else "")
        )
    lines.append(f"model puts one bin at {model:.1f} positions"
                 + (f"; observed {observed:.1f}" if observed is not None else ""))
    lines.append("")
    try:
        low, high = result.offset_window(min_snr_db)
    except ValueError:
        lines.append("RESULT: no single constant offset fits these samples.")
        if statistics["range"] > 1.0:
            lines.append(f"  Per-position offsets span {statistics['range']:.3f} bins. A constant offset")
            lines.append("  can only produce a span below 1.0, so the offset varies with window position.")
        if observed is not None and abs(observed - model) > 0.5:
            lines.append(f"  Peak transitions are {observed:.1f} positions apart but a constant offset")
            lines.append(f"  requires exactly {model:.1f}. See docs/kiwi-protocol.md.")
        lines.append(f"  Mean offset over the sweep is {statistics['mean']:+.3f} bins.")
        return "\n".join(lines)
    lines.append(f"offset in ({low:.4f}, {high:.4f}]  width {high - low:.4f} bins "
                 f"({(high - low) * result.span.bin_width_hz:.2f} Hz)")
    lines.append(f"center estimate {(low + high) / 2:.4f} bins")
    if not result.crossed_bin_boundary(min_snr_db):
        lines.append("WARNING: the peak never changed bin, so the sweep did not cross a boundary")
        lines.append("         and has not improved on a single measurement. Widen --steps or --step-hz.")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = build_arg_parser()
    args = parser.parse_args(argv)

    if args.analyse is not None:
        try:
            result = load_sweep_fixture(args.analyse, reference_khz=args.reference_khz)
        except LiveCaptureError as exc:
            parser.error(str(exc))
        if args.export_samples is not None:
            export_samples(result, args.export_samples, min_snr_db=args.min_snr_db)
        if args.json:
            print(json.dumps(result.summary(args.min_snr_db), indent=2, sort_keys=True))
        else:
            print(format_sweep_report(result, args.min_snr_db))
        return 0

    config = config_from_args(args)
    try:
        if args.dry_run:
            if args.output is not None:
                config.validate()
            print(json.dumps(config.dry_run_plan(), indent=2, sort_keys=True))
            return 0
        if args.output is None:
            parser.error("--output is required for a live sweep")
        config.validate()
        if not args.allow_live:
            parser.error("live sweep requires --allow-live; use --dry-run for a plan")
        path = asyncio.run(sweep_waterfall_window(config, allow_live=True))
        result = load_sweep_fixture(path, reference_khz=config.reference_khz)
        if args.json:
            print(json.dumps(result.summary(config.min_snr_db), indent=2, sort_keys=True))
        else:
            print(f"wrote {path}\n")
            print(format_sweep_report(result, config.min_snr_db))
        return 0
    except LiveCaptureError as exc:
        parser.error(str(exc))
    return 2


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
