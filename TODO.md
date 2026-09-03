# TODO

## Current slice — Paired TUI operation design

Branch: `feature/shared-radio-session`, based on the newly updated `main` integration branch.

Completed in this branch:

- Added UI-neutral paired transport coordinator and typed interactive session model.
- Added `ClientController` state and generation-aware audio-only lifecycle adapters.
- TUI dashboard can display desired/active receiver, SND/W/F status, audio state, and W/F zoom while retaining legacy operation details.
- Existing receiver-switch rollback behavior remains harnessed.
- Full harness: 306 tests passed.

Next goal: design the smallest paired TUI operation that replaces startup `play-bg` when W/F is requested, without embedding graphics yet.

Done criteria:

- Define explicit start/stop command/API semantics for audio-only versus paired interactive sessions.
- Reuse `PairedSessionCoordinator`; do not duplicate SND/W/F ordering logic.
- Publish W/F metadata/frame cadence metrics to the controller without terminal-renderer dependencies.
- Route typed controller SND/W/F commands to the correct queues.
- Add fake-runner lifecycle tests before exposing any live command.
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
