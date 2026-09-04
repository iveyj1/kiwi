# TODO

## Current slice — Timed native fixture playback

Branch: `feature/shared-radio-session`, based on the newly updated `main` integration branch.

Validated baseline:

- Fixture image, orientation, scaling, resize behavior, and PySide6 window are acceptable.
- `q`/Esc/Ctrl+Q/window-manager close now exit successfully in attended use.

Next goal: animate fixture rows through the native snapshot boundary at a controlled rate.

Done criteria:

- Publish fixture rows incrementally at configurable FPS without network access.
- Consume only the latest snapshot generation on each GUI timer tick.
- Render direct RGB without PNG/base64.
- Show source/presentation generation and basic cadence status.
- Preserve bounded history and clean timer/window shutdown.
- Add pure timeline/controller tests plus a dry-run demonstration.

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
