# Native GUI toolkit benchmark plan

## Purpose

Choose a Linux desktop raster frontend only after measuring a small fixture-driven prototype. The protocol, paired session, controller, and `WaterfallSnapshotPublisher` remain toolkit-independent.

## Candidates

Benchmark no more than three initial candidates:

- **Tkinter** — usually available with Python, small integration cost; image-update throughput may be limiting.
- **PySide6 / Qt** — mature image, input, layout, and packaging support; large dependency footprint.
- **pygame/SDL** — direct pixel/texture updates and modest UI assumptions; controls and desktop widgets require more project code.

Do not add any candidate to default project dependencies during the benchmark.

## Toolkit-independent baseline

Run the common synthetic publisher workload without opening a window:

```bash
.kiwi-venv/bin/python tools/waterfall_gui_benchmark.py \
  --history-rows 200,400,800 --width 1024 --frames 1200 \
  --source-fps 20 --consumer-fps 20
```

The command emits one JSON result per history depth with produced/presented counts, coalesced generations, virtual duration, elapsed throughput, and mean/p95 publish cost. Set `--consumer-fps` below `--source-fps` to verify deterministic latest-generation coalescing.

Initial no-window run on the development machine:

```text
Rows | Frames | Mean publish ms | p95 publish ms | Throughput frames/s
200  | 1200   | 0.140           | 0.171          | 6448
400  | 1200   | 0.159           | 0.222          | 5801
800  | 1200   | 0.158           | 0.197          | 6044
```

These numbers measure snapshot publication only, not color conversion or GUI upload.

## Fixed workload

Use captured/synthetic data only:

- 1024 bins per W/F row.
- Histories of 200, 400, and 800 rows.
- 20 requested updates/sec for 60 seconds.
- Half-width and full-width window layouts.
- Existing deterministic palette plus tuned/passband/cursor overlays.
- Recenter/zoom snapshot changes with rows retaining original frequency mappings.

Use `WaterfallSnapshotPublisher`; do not create network or audio sessions in the benchmark.

## Measurements

Record for each toolkit and history size:

- achieved presentation FPS,
- process CPU and resident memory,
- time to convert/upload one snapshot,
- queued or dropped/coalesced updates,
- resize latency,
- input-to-marker latency,
- shutdown cleanliness,
- installed dependency size and startup time.

A toolkit must keep producer memory bounded and consume only the latest newer snapshot when it falls behind.

## Functional checks

- Direct RGB or texture upload; avoid PNG/base64 in the native path.
- Resize without corrupting frequency mapping.
- Keyboard and mouse frequency selection.
- Exact direct frequency entry.
- Tuned/passband/cursor overlays.
- A path to old-history zoom remapping and optional jitter-buffer controls.
- Errors/status updates delivered without blocking display refresh.

## Initial acceptance target

- Sustain at least 20 FPS for a 1024×400 raster on the development machine.
- Remain responsive while snapshots arrive faster than display capacity.
- No unbounded queue growth.
- Clean window close and worker wakeup.
- Keep toolkit-specific code outside transport, protocol, and session modules.

## Result format

Add one table to this document after running prototypes:

```text
Toolkit | Size | FPS | CPU | RSS | Upload ms | Drops | Startup ms | Installed MB | Notes
```

Select a toolkit only after the same workload has been run for all retained candidates.
