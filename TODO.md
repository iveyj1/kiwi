# TODO

## Current slice — Validate integrated Kitty fixture shell

Branch: `feature/shared-radio-session`, based on the newly updated `main` integration branch.

Implemented:

- `kiwi-console` fixture-only curses shell with a reserved upper Kitty image.
- Adaptive frequency ruler, visible-preset ruler, compact status/controls, and direct-entry prompt.
- Main/fine selection, tune, center, zoom, direct-frequency, and preset actions through shared session state.
- Absolute saved-cursor Kitty placement, generation coalescing, resize invalidation, and explicit image deletion.
- Pure layout/ruler/presenter tests and Qt-free/network-free dry-run.

Done criteria:

- Full harness, compile, and diff checks pass.
- Attended Kitty run confirms image placement above text, ruler alignment, controls, resize, and clean exit/restoration.
- Correct any curses/Kitty interaction before integrating paired live session.
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
