# TODO

## Current slice — Validate native fixture controls

Branch: `feature/shared-radio-session`, based on the newly updated `main` integration branch.

Implemented:

- Tuned, passband-edge, and selected-frequency overlays over incremental direct RGB.
- Main/small keyboard cursor steps, tune-selected, direct frequency entry, local recenter, and local zoom.
- All control changes dispatch through `RadioSessionManager`; generated protocol commands are not sent.
- Default fixture-mapped center/zoom initialization and CLI radio-state overrides.

Done criteria:

- Full harness, compile, and diff checks pass.
- Attended animation confirms overlay visibility and keyboard/widget behavior.
- Confirm controls do not interfere with exit or timed presentation.
- Record any scaling/input corrections before starting paired live integration.
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
