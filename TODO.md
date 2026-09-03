# TODO

## Current slice — Native GUI candidate selection

Branch: `feature/shared-radio-session`, based on the newly updated `main` integration branch.

Completed in this branch:

- Added shared paired coordinator, typed session/controller/TUI lifecycle, headless `radio-bg`, and renderer-neutral snapshots.
- Added toolkit-independent `tools/waterfall_gui_benchmark.py` with deterministic 1024-bin workloads, latest-generation coalescing, and JSON metrics.
- Added 200/400/800-row no-window baseline results to `docs/native-gui-benchmark.md`.
- Current environment has no Tkinter, PySide6, or pygame installed; no GUI dependency was added automatically.

Next goal: select the first isolated GUI benchmark candidate and dependency strategy before implementation.

Decision criteria:

- Prefer direct RGB/texture upload and reliable 1024×400 at 20 FPS.
- Keep the candidate optional and outside default dependencies.
- Account for installation/package size, Linux integration, input/widgets, and future zoom-history remapping.
- Compare at least two viable candidates with the common workload before committing to the production frontend.

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
