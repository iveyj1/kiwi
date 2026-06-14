# TODO

## Current slice

Goal: Fix TUI keymap quit while live playback is active.

Done criteria:

- Keymap `q` / configured `quit` action requests cooperative background stop before ending the TUI.
- Command-mode `quit`, `q`, `qu`, and `exit` use the same safe TUI quit path.
- If the background operation does not stop quickly, keep TUI running and report that stop is still in progress.
- Cover safe quit behavior with harness tests.
- Update the example root config and docs/dev-log.

Test command: `python3 -m pytest tests/harness tests/audio tests/protocol`

Live-radio needed: no; harness-first TUI shutdown work.

Docs to update: root `config.toml`, `docs/roadmap.md`, `docs/user-guide.md`, `docs/dev-log.md`

## Next

- Inspect `kiwiclient/` and identify SND/audio connection path.
- Define fixture format for KiwiSDR control and stream messages.
- Add first parser test using synthetic or captured SND data.
- Add first local live-radio capture only after the harness path exists.

## Later

- Basic desktop client: connect, tune, mode, audio.
- Waterfall decode and rendering.
- Recording pipeline.
- MF/LF beacon detector.
- Long-integration/correlation analysis.
