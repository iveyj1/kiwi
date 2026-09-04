# TODO

## Current slice — Correct native fixture controls

Branch: `feature/shared-radio-session`, based on the newly updated `main` integration branch.

Attended findings:

- Marker lines need two-pixel width.
- Tune, center, and zoom lacked visible raster behavior; zoom below 1 appeared to freeze.
- Initial focus lands in frequency entry and blocks global keymaps.

Done criteria:

- Draw two-pixel tuned, passband-edge, and selection markers.
- Make fixture zoom/recenter visibly remap the captured raster, with black fill outside captured coverage.
- Show tuned marker after tune rather than hiding it under coincident selection.
- Keep bounded zoom responsive at zero and preserve timed presentation.
- Start with display focus; `f` focuses entry and accepted direct entry returns focus to display.
- Add remap/control/focus policy tests and request an attended retry.
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
