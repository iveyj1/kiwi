# TODO

## Current slice — ClientController session adapter

Branch: `feature/shared-radio-session`, based on the newly updated `main` integration branch.

Completed in this branch:

- Added UI-neutral `PairedSessionCoordinator` and migrated `kiwi-wf-terminal` lifecycle ownership.
- Added immutable `RadioSessionSnapshot`, generation-aware errors, typed lifecycle/control actions, and pure SND/W/F command routing.
- Full harness: 302 tests passed.

Next goal: adapt existing `ClientController` state/actions to the new session manager without changing current TUI operation.

Done criteria:

- Initialize the shared session snapshot from `ClientState` and waterfall config inputs without reverse UI dependencies.
- Keep legacy `RadioSessionState` responses compatible during migration.
- Route controller tune/mode/filter state changes through one synchronization adapter while preserving existing live playback command tests.
- Expose paired SND/W/F status fields in controller status output without requiring live transports.
- Add pure controller harness coverage and keep existing receiver-switch rollback tests passing.
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
