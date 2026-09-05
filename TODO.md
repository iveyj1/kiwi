# TODO

## Current slice — Existing TUI behavior in integrated console

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

Next goal: model the lower console on the existing TUI where it fits.

Done criteria:

- Reuse existing dashboard/status rendering and configurable keymap dispatch rather than maintaining console-only equivalents.
- Add command mode with existing parsing, history, hints, and error reporting.
- Recall/store presets and receiver registers through `ClientController`, preserving persistence semantics.
- Add audio toggle/state and volume controls; live audio currently requires startup `--audio`.
- Add visible manual colormap limits using existing render-min/max controls, runtime adjustment, and a percentile-based auto-scale mode with bounded smoothing.
- Keep waterfall selection/tune/recenter behavior explicit where it intentionally differs from direct TUI tuning.
- Keep exact frequency/preset tick stems aligned, omit unit suffixes and irregular edge labels, and retain only the high-resolution raster passband bracket.
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
