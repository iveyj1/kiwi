# TODO

## Current slice

Goal: Add system-volume read-before-step, presets, and persisted startup state.

Done criteria:

- `volume-step` reads current system output volume before applying its delta.
- Add `store <n>`, `store all <n>`, and `recall <n>` commands.
- Minimal presets store receiver/frequency/mode/filter; all presets store full radio/client state.
- Add TUI keymap digit sequences `<n>s`, `<n>S`, and `<n>r`.
- Save last full radio state and presets on TUI safe exit.
- Restore startup state from config: last state, default state, or preset.
- Cover behavior with harness tests.
- Update root `config.toml` and docs.

Test command: `python3 -m pytest tests/harness tests/audio tests/protocol`

Live-radio needed: no; harness-first UI/state work.

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
