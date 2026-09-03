# TODO

## Current slice — Paired lifecycle adapter

Branch: `feature/shared-radio-session`, based on the newly updated `main` integration branch.

Completed in this branch:

- Added UI-neutral paired transport coordinator and typed interactive session model.
- `ClientController` now initializes/synchronizes shared receiver, tuned/selected frequency, mode, passband, CW offset, and command precision.
- Controller `status` exposes the shared snapshot while retaining legacy `RadioSessionState` compatibility.
- Full harness: 304 tests passed.

Next goal: map legacy playback start/stop/failure/switch transitions into generation-aware paired lifecycle state, then expose those fields in the TUI dashboard without starting W/F yet.

Done criteria:

- Map current audio-only `BackgroundOperation` states accurately as SND state with W/F marked inactive/waiting as appropriate.
- Preserve receiver-switch recovery and rollback behavior.
- Prevent stale worker errors from replacing a newer generation.
- Render paired desired/active receiver and SND/W/F status in pure TUI dashboard tests.
- Do not change live startup defaults or connect to a receiver.

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
