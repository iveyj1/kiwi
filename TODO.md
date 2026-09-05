# TODO

## Current slice — Existing TUI lower-panel behavior

Branch: `feature/shared-radio-session`, based on the newly updated `main` integration branch.

Completed and validated:

- Fixed zoom-transition history so every retained/new row remaps from its own captured frequency coordinates instead of the newest row's scale.
- Fixed live tune state being overwritten during legacy/shared status synchronization.
- `f` and selection+Enter now tune without implicit recenter; `c` remains explicit center.
- Added a high-resolution Kiwi-style raster tuning strip so sub-cell indicator movement remains visible.
- Controller-backed `--allow-live --receiver <local>` mode uses one paired SND/W/F worker and bounded snapshots.
- Typed session commands route through a public controller API; shutdown stops and joins the worker.
- Fake-operation coverage includes frame delivery, command routing, failure, null/audio startup, and idempotent cleanup.
- Two bounded local `10.0.0.40:8073` runs displayed actual 5000 kHz W/F data with synchronized running status.
- Automated live screenshot: `docs/screenshots/kiwi-console-live-local.png`.

Completed:

- Set integrated-console selection defaults to 1.0/0.1 kHz with explicit CLI overrides, independent of local config step-pair ordering.
- Reused existing live TUI key dispatch, command editing/history, contextual hints, preset/store/receiver prefixes, configured non-waterfall actions, and error handling in the lower panel.
- Added runtime manual min/max dB adjustment and percentile-based automatic scaling with bounded cadence, smoothing, padding, and minimum range.
- Replaced the prototype 5x7 scale font with anti-aliased Pillow/FreeType DejaVu Sans Mono; retained deterministic bitmap fallback and explicit backend/font options.
- Composed W/F history, passband/selection strip, frequency ticks/labels, and preset stems/labels into one 1024-bin Kitty image.
- Added deterministic dependency-free 5x7 bitmap text, round major ticks, exact shared frequency columns, and pixel-coordinate collision rejection.
- Removed redundant terminal-cell scale rows and returned that space to curses controls.
- Updated automated Kitty fixture screenshot.

Next goal:

- Refine compact dashboard/status presentation using existing TUI model data.
- Verify preset/receiver persistence and add explicit audio toggle/state controls; command/history/hints and configurable dispatch are now integrated for live mode.
- Keep waterfall-specific selection/tune/recenter behavior explicit where it intentionally differs from direct TUI tuning.
- Add pure/fake-operation tests before another attended local session.

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
