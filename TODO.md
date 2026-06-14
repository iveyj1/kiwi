# TODO

## Current slice

Goal: Start persistent live-mode settings and TUI for Milestone 6.

Done criteria:

- Add persistent client-state fields for live duration and max SND frames.
- Add `duration`, `frames`, and `dashboard` commands to the scriptable client shell.
- Ensure play/record/capture plans and executable commands reuse persistent live settings.
- Add a testable text dashboard renderer and a thin curses TUI runner.
- Add `--tui` and `kiwi-tui` entry points.
- Cover persistent settings and dashboard rendering with pytest.

Test command: `python3 -m pytest tests/harness tests/audio tests/protocol`

Live-radio needed: no

Docs to update: `docs/roadmap.md`, `docs/user-guide.md`, `docs/dev-log.md`

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
