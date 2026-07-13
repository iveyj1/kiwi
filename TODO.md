# TODO

## Current slice

Goal: Support sub-Hz Kiwi tuning commands.

Done criteria:

- Add configurable Kiwi modulation command frequency precision.
- Preserve existing 3-decimal default command formatting unless configured otherwise.
- Root config enables 4-decimal command frequency formatting for local sub-Hz step testing.
- Active playback retune commands and live setup plans use configured command precision.
- Harness tests prove a sub-Hz step emits a sub-Hz `SET mod ... freq=` value.
- Update root `config.toml`, user docs, radio parameter docs, Kiwi protocol notes, and dev log.

Test command: `python3 -m pytest tests/protocol/test_commands.py tests/harness/test_config.py tests/harness/test_client_app.py tests/harness/test_tui.py && python3 -m pytest`

Live-radio needed: no; command encoding behavior only.

Docs to update: `docs/user-guide.md`, `docs/radio-parameters.md`, `docs/kiwi-protocol.md`, `docs/dev-log.md`.

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
