# TODO

## Current slice — Native fixture controls

Branch: `feature/shared-radio-session`, based on the newly updated `main` integration branch.

Completed:

- Added static and timed fixture playback through `WaterfallSnapshotPublisher`.
- Added incremental native rasterization that colors only newly presented rows.
- Added `--animate --fps`, source/presented generation status, bounded history, and clean timer shutdown.
- Preserved direct RGB/QImage presentation without PNG/base64.

Next goal: add basic fixture-only native frequency/cursor controls before live integration.

Done criteria:

- Draw tuned, passband, and selected-frequency overlays using shared state.
- Support keyboard cursor steps, direct frequency entry, recenter/zoom state, and visible control status without sending network commands.
- Keep control actions routed through `RadioSessionManager`.
- Add pure model/action tests and an attended animated fixture demo.
- Do not connect to a receiver.

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
