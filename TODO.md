# TODO

## Current slice

Goal: Per-mode passbands and CW heterodyne tuning architecture.

Done criteria:

- Carry low/high cut frequencies separately per mode.
- Defaults: AM `-5000..5000`, USB `0..3000`, LSB `-3000..0`, CW configured by current filter settings.
- `filter <low> <high>` updates only the current mode passband.
- Mode switching restores that mode’s saved/default passband.
- CW user-facing frequency is passband center; Kiwi radio command frequency is offset by configurable `cw_offset_hz`.
- Root `config.toml`, user docs, radio parameter docs, and dev log are updated.

Test command: `python3 -m pytest tests/harness/test_config.py tests/harness/test_client_app.py tests/harness/test_tui.py tests/protocol/test_commands.py && python3 -m pytest`

Live-radio needed: no; command/planning behavior only.

Docs to update: `docs/user-guide.md`, `docs/radio-parameters.md`, `docs/dev-log.md`, `docs/kiwi-protocol.md` if command semantics change.

## Next

- Inspect the generated static PNG and decide whether bin orientation/scaling is plausible.
- Investigate W/F sequence semantics: local fixture repeated `seq=0` for two frames despite valid 1024-bin payloads.
- Add frequency/bin mapping from local W/F metadata (`center_freq`, `bandwidth`, `wf_fft_size`, zoom/start).
- Decide whether to integrate a compact waterfall pane into the curses TUI or keep standalone live preview first.

## Later

- Basic desktop client: connect, tune, mode, audio.
- Waterfall decode and rendering.
- Recording pipeline.
- MF/LF beacon detector.
- Long-integration/correlation analysis.
