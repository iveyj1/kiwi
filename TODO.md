# TODO

## Current slice

Goal: Harden modified-key handling and add config-driven live limits and receiver policy.

Done criteria:

- Shift-right/shift-left are recognized where curses reports them as distinct keys.
- Unknown modified-key/escape-sequence inputs are ignored safely in keymap mode.
- TOML config supports live `duration_seconds` and `max_frames`, where `0` means unlimited.
- TOML config supports receiver restrictions, defaulting to local receivers and allowing explicit unrestricted receiver use.
- TUI-created client state applies configured live limits and receiver policy.
- Live play/record/capture validation and loops support configured limits and receiver policy.
- Cover key handling, config parsing, controller wiring, and validation with pytest.

Test command: `python3 -m pytest tests/harness tests/audio tests/protocol`

Live-radio needed: no; harness-first UI/config work.

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
