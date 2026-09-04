# TODO

## Current slice — Integrated Kitty waterfall/TUI fixture shell

Branch: `feature/shared-radio-session`, based on the newly updated `main` integration branch.

Direction:

- Use Kitty as the initial supported terminal for the primary integrated interface.
- Retain PySide6 only as an optional prototype and preserve the standalone terminal/TUI fallbacks.
- Prefer one terminal process and one shared paired session over duplicate coordinated windows.

Done criteria:

- Define a curses-owned layout with a reserved Kitty waterfall rectangle above status, preset/frequency rulers, controls, and command/log regions.
- Add a fixture-only integrated shell before any live receiver work.
- Keep all terminal writes on the UI thread and coalesce raster updates.
- Route input through the shared session manager and existing TUI key/action policies.
- Handle resize, alternate-screen cleanup, image deletion, and terminal restoration deterministically.
- Add fake-terminal/fixture harnesses before an attended Kitty test.
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
