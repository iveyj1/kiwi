# TODO

## Current slice — Controller-backed live Kitty waterfall harness

Branch: `feature/shared-radio-session`, based on the newly updated `main` integration branch.

Validated/implemented:

- Integrated Kitty fixture shell looks good in attended use.
- Removed superimposed image markers from the console and added a green Kiwi-style external passband bracket with a separate selection pointer.
- Captured `docs/screenshots/kiwi-console-fixture.png` from an automated Kitty fixture run.

Goal: feed the integrated console from the existing controller-owned paired session without duplicating TUI behavior or receiver connections.

Done criteria:

- Reuse TUI startup state, presets, command mode, dashboard/status concepts, and keymaps where they fit the waterfall layout.
- Add an explicit `--allow-live` path using `ClientController` `radio-bg` and its bounded waterfall publisher.
- Keep curses/Kitty rendering on the UI thread while paired network/audio workers stay off-thread.
- Route tune/recenter/zoom/audio/preset operations through public controller APIs.
- Stop and join paired work deterministically on every console exit path.
- Cover live startup, latest-snapshot rendering, command routing, failure, and cleanup with fake operations before radio use.
- Then perform one short attended test on a local receiver only and record a fixture/observations.

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
