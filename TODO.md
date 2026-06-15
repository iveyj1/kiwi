# TODO

## Current slice

Goal: Move receiver/playback switch orchestration out of TUI helpers and into controller-owned radio session methods.

Done criteria:

- Add an explicit controller-side radio session state snapshot for desired receiver, active receiver, playback intent, lifecycle mode, and current session error.
- Add `ClientController.switch_receiver(..., preserve_playback=True)` to own idle, active-playback, failed-playback, and busy-rollback transitions.
- Simplify TUI receiver-register handling so it delegates receiver-switch policy to the controller.
- Preserve harness coverage for idle switch, active switch restart, busy rollback, failed-playback recovery, and stale-error clearing.
- Update architecture/session docs, roadmap, and dev-log.

Test command: `python3 -m pytest tests/harness/test_client_app.py tests/harness/test_tui.py && python3 -m pytest`

Live-radio needed: no; use controller/TUI harness tests first.

Docs to update: `docs/radio-session-state.md`, `docs/roadmap.md`, `docs/dev-log.md`.

## Next

- Consider displaying desired vs active receiver/session mode in the TUI dashboard.
- Consider adding operation generation ids if stale-error handling grows beyond single playback worker recovery.

## Later

- Basic desktop client: connect, tune, mode, audio.
- Waterfall decode and rendering.
- Recording pipeline.
- MF/LF beacon detector.
- Long-integration/correlation analysis.
