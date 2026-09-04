# TODO

## Current slice — Native fixture-window exit controls

Branch: `feature/shared-radio-session`, based on the newly updated `main` integration branch.

Observed validation:

- Fixture image, orientation, scaling, and general PySide6 window behavior were acceptable.
- User could not exit using the attempted interaction.

Done criteria:

- Make `q`, Esc, and Ctrl+Q close the fixture window.
- Explicitly quit the application when the last window closes.
- Keep normal window-manager close behavior.
- Add pure key-policy coverage without requiring Qt/display imports.
- Document controls, run full harness, and request a short attended retry.

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
