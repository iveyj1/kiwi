# TODO

## Current slice — Renderer snapshot boundary

Branch: `feature/shared-radio-session`, based on the newly updated `main` integration branch.

Completed in this branch:

- Added shared paired coordinator, typed session model, and controller/TUI lifecycle adapters.
- Added `radio-bg` for headless paired SND/W/F operation, distinct stream command routing, W/F status/metadata metrics, and paired receiver restart.
- Added `wf-center` and `wf-zoom` controller/TUI commands.
- Continuous headless and terminal W/F operation no longer accumulates an unbounded in-memory fixture unless saving was requested.
- Full harness baseline before final documentation: 310 tests passed.

Next goal: define a bounded renderer-neutral waterfall snapshot publisher that a native GUI or optional terminal pane can consume without owning transport state.

Done criteria:

- Publish immutable mapped frame/history snapshots independently from Kitty/curses.
- Bound producer/consumer memory and coalesce superseded display snapshots.
- Preserve numeric history needed for future zoom remapping.
- Add fixture/fake-consumer tests and a small native toolkit benchmark plan before selecting a GUI dependency.
- Do not embed Kitty graphics into curses in this slice.

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
