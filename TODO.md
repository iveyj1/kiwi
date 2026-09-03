# TODO

## Current slice — PySide6 fixture-window validation

Branch: `feature/shared-radio-session`, based on the newly updated `main` integration branch.

Completed:

- Benchmarked PySide6 and pygame-ce direct RGB at 1024×200/400/800 and selected PySide6 provisionally.
- Kept both in isolated optional dependency extras; default installation is unchanged.
- Added fixture-only `kiwi-gui` using direct `QImage`/`QPixmap` presentation.
- Added model/dry-run harness coverage requiring no Qt import or display server.

Validation goal:

- Run the attended 1024×400 fixture window on the real desktop.
- Confirm image orientation, scaling, resize behavior, frequency text, clean close, and acceptable startup/dependency behavior.
- Record observed CPU/memory if convenient.
- Do not add live receiver/audio integration until this static window is accepted.

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
