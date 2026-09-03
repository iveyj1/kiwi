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

## Adapter comparison — 2026-09-03

Headless/dummy direct-RGB test, 400 alternating frames per size. This measures toolkit conversion/event processing without compositor pacing and therefore demonstrates margin rather than visible FPS.

```text
Toolkit   | Size     | mean ms | p95 ms | startup ms* | Installed MB | Notes
PySide6   | 1024x200 | 0.199   | 0.431  | 82.6        | 226.2        | Essentials + shiboken only
PySide6   | 1024x400 | 0.412   | 0.609  | 1.2         | 226.2        | QApplication reused
PySide6   | 1024x800 | 0.827   | 1.122  | 1.8         | 226.2        | QApplication reused
pygame-ce | 1024x200 | 0.419   | 0.540  | 52.7        | 32.2         | SDL dummy driver
pygame-ce | 1024x400 | 0.844   | 1.115  | 31.9        | 32.2         | display recreated
pygame-ce | 1024x800 | 1.510   | 2.412  | 34.3         | 32.2         | display recreated
```

`*` First-start and repeated-start behavior differ, so startup values are descriptive rather than directly averaged.

Both candidates have ample direct-RGB margin over the 20 FPS requirement. PySide6 is selected for the first GUI prototype despite its larger optional footprint because it is faster here and supplies mature controls, layouts, keyboard/mouse handling, accessibility, and packaging primitives that pygame would require the project to build. Keep pygame-ce as a smaller fallback candidate until an attended PySide6 window test confirms Linux display behavior.

Install candidates only when benchmarking:

```bash
.kiwi-venv/bin/python -m pip install -e '.[gui-benchmark]'
```

Run either adapter with `--no-headless` for an attended compositor/window test.

## Result format

Add one table to this document after running prototypes:

```text
Toolkit | Size | FPS | CPU | RSS | Upload ms | Drops | Startup ms | Installed MB | Notes
```

Select a toolkit only after the same workload has been run for all retained candidates.
