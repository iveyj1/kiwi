# TODO

## Current slice — Controller session manager foundation

Branch: `feature/shared-radio-session`, based on the newly updated `main` integration branch.

Completed in this branch:

- Added UI-neutral `PairedSessionCoordinator` with shared timestamp resolution.
- Migrated `kiwi-wf-terminal` to SND-first/W/F-second coordinated startup and cleanup.
- Covered readiness failure, cancellation, W/F failure, post-ready SND error policy, and separate command queues with fake runners.
- Full harness: 296 tests passed.

Next goal: introduce the controller-owned session/action model without changing existing TUI behavior.

Done criteria:

- Define immutable desired/active paired-session state and generation-aware errors.
- Define typed tune, recenter, zoom, audio, and direct-frequency actions independent of curses and Kitty.
- Add pure state-transition/command-routing tests.
- Keep existing `RadioSessionState` compatibility while preparing migration from raw `BackgroundOperation` inference.
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
