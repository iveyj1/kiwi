# TODO

## Current slice — PySide6 fixture GUI prototype

Branch: `feature/shared-radio-session`, based on the newly updated `main` integration branch.

Completed comparison:

- Both PySide6 and pygame-ce exceed the 20 FPS direct-RGB target in headless benchmarks.
- PySide6 Essentials measured roughly 0.41 ms mean / 0.61 ms p95 at 1024×400 versus pygame-ce 0.84/1.11 ms.
- PySide6 Essentials is much larger (about 226 MB versus 32 MB), but is selected for the first prototype because mature widgets/layout/input avoid building a desktop UI framework inside the project.
- Both remain optional extras; default installation is unchanged.

Next goal: add a fixture-only PySide6 window using `WaterfallSnapshotPublisher` and existing raster/overlay code.

Done criteria:

- Keep PySide6 imports optional and report a clear installation command.
- Render captured fixture history via direct `QImage`/`QPixmap`, not PNG/base64.
- Add basic frequency/status text and clean window close.
- Harness the model/controller boundary without requiring a display server.
- Provide an attended fixture demo command; no receiver connection in this slice.

## Plan

See `docs/ui-integration-plan.md`.

1. Shared paired-session coordinator.
2. Controller-owned `RadioSessionManager` and typed actions.
3. TUI lifecycle/status integration without embedded graphics first.
4. Native graphical frontend benchmark/prototype.
5. Optional curses-aware Kitty pane if still valuable.
6. One-stream SND consumer fan-out for playback/recording/detection.

## Deferred waterfall questions

- Measure whether zoom-dependent vertical slowdown is receiver cadence or presentation cadence.
- Evaluate a small optional bounded W/F jitter/playout buffer and its smoothness/latency tradeoff.
- Remap retained history across zoom/recenter changes like the KiwiSDR web client, resampling overlap and filling uncovered frequencies with black.

## Validation baseline

- `main` now contains the tested `wf1` integration history.
- Latest full harness before this slice: 289 tests passed.
- `config.toml` remains intentionally unchanged.
