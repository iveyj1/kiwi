# TODO

## Current slice — Shared paired-session coordinator

Branch: `feature/shared-radio-session`, based on the newly updated `main` integration branch.

Goal: extract Kiwi paired SND/W/F lifecycle ownership from the terminal UI into a reusable, UI-neutral coordinator.

Done criteria:

- Keep one shared session timestamp in the supplied SND/W/F configs.
- Start primary SND and await authenticated readiness before starting paired W/F.
- Abort without opening W/F when SND fails before readiness.
- Keep separate bounded-lifecycle SND and W/F tasks and command queues.
- Stop SND cleanly when W/F completes, fails, or is cancelled.
- Report SND failure after readiness independently while allowing W/F policy to remain explicit.
- Add deterministic fake-runner tests before moving terminal behavior.
- Migrate `kiwi-wf-terminal` to the coordinator without changing controls, rendering, or live guardrails.
- Run targeted and full harnesses; no automatic live receiver connection.

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
