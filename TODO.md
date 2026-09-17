# TODO

## Current slice — Cleanup and main merge preparation

Goal: consolidate the tested interactive client and local-address migration for review and merge into `main`, without merging or modifying `main` yet.

Done criteria: current planning/handoff docs agree; receiver defaults and presets have offline regression coverage; full tests, compilation, and diff checks pass; feature branch changes are committed; ancestry/merge readiness is recorded.

## Completed baseline

- Shared controller-owned paired SND/W/F session and typed tuning/view actions.
- Primary integrated Kitty/curses `kiwi-console`; optional native GUI prototype.
- Browser-style `/VER` bootstrap and SND `badp=0` gate before W/F startup.
- Stalled SND stop-fade regression fixed; bounded cooperative primary teardown with cancellation fallback.
- Double-buffered Kitty presentation, graphical tuning scale, signed CW passband and distinct nominal/RX markers.
- Immediate tuning, offscreen frequency-entry recentering, and one-span Up/Down/Page tuning.
- Runtime audio toggle, volume, receive-mode prefix, presets, receiver switching, and saved state.
- Controls remain usable before the first waterfall frame.
- Public-directory parser/export and checked receiver browser links.
- Local receivers: `.41`, `.42`, `.43` on port 8073. `.41` remains the general default; `.43` is preferred for local NDB work in its user-reported 4-channel configuration.
- Historical capture addresses are preserved, including retired `.40`.

## Remaining reliability work

- First-message, first-frame, and stalled-stream deadlines with explicit diagnostics.
- Rapid-switch stress coverage including stalled authentication and WebSocket opening/closing. One user-reported hang after the stop-fade fix remains unconfirmed, not dismissed as operator error.
- Audit every frontend's paired bootstrap, network guard, and cancellation path; shared helpers alone do not prove identical lifecycle behavior.
- Verify preset/receiver persistence during ordinary use.
- Complete reference-tool comparisons only when they resolve a specific outstanding compatibility question. No unpaired two-allocation fallback or reconnect loops.

## Waterfall presentation — deferred, not a merge requirement

- Measure acquisition cadence separately from terminal presentation (the usual console command presents at 5 Hz).
- Evaluate 15–20 Hz presentation, then an optional bounded 150–250 ms playout buffer if needed. Reset on view/receiver changes, freeze on starvation, and drop backlog after terminal stalls.
- Do not synthesize signal measurements to smooth scrolling.
- Expect 8-channel public receivers. User reports reduced maximum zoom (approximately 11 versus 14) and slower W/F cadence; exact values depend on firmware/mode and need metadata-backed tests, not hardcoded assumptions.
- Audit `zoom_max` versus `zoom_cap` propagation through parser, controller, and frontend before claiming full mode-dependent limit support.

## NDB/analysis direction

- Use received SND/IQ data for closer signal analysis; W/F is a navigation/overview display, not the measurement pipeline.
- Prefer local `10.0.0.43:8073` for NDB development; do not require its 4-channel W/F capabilities for public operation.
- Next architectural step: one SND consumer fan-out for playback, recording, and detection.
- Build the first beacon detector against synthetic/captured fixtures before live testing; long-term integration/correlation remains planned.

## Validation

Cleanup validation: 401 tests passed; compileall and diff checks passed. Local `main` (`0daae2f`) is an ancestor of the feature branch, allowing fast-forward integration if unchanged. Remote refs were not refreshed; check them before the actual merge. No merge or live-radio testing was performed. See `docs/dev-log.md` and `docs/handoff.md`.
