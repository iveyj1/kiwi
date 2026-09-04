# TODO

## Current slice — Native one-pixel-per-frame vertical scale

Branch: `feature/shared-radio-session`, based on the newly updated `main` integration branch.

Validated:

- Timed fixture animation works in the attended PySide6 window.

Goal: make one physical display-pixel row per W/F frame the default when the requested history fits the available screen.

Done criteria:

- Add a pure DPI-aware source-row-to-logical-height policy.
- Default to 1.0 physical pixel per W/F frame.
- Cap display height to available screen space when exact 1:1 cannot fit.
- Keep horizontal resizing independent from vertical row scale.
- Add an explicit CLI override and report effective scale in status/dry-run output.
- Add harness coverage and an attended retry command; no receiver connection.

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
