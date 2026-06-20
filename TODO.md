# TODO

## Current slice

Goal: Per-mode tuning step pairs and TUI step cycling.

Done criteria:

- Each mode has current normal/small tuning step sizes.
- Defaults: AM `5000/1000`, USB/LSB `1000/100`, CW `100/10`.
- Normal left/right arrows and `h/l` use the current normal step; shifted arrows and `H/L` use the current small step.
- `t` increases to the next configured step pair for the current mode; `T` decreases to the previous pair; both clamp at the list ends.
- Dashboard/status display current steps as `Step: normal/small Hz`.
- Additional per-mode step pairs are configurable in `config.toml`.
- Root `config.toml`, user docs, radio parameter docs, and dev log are updated.

Test command: `python3 -m pytest tests/harness/test_config.py tests/harness/test_client_app.py tests/harness/test_tui.py && python3 -m pytest`

Live-radio needed: no; TUI/control behavior only.

Docs to update: `docs/user-guide.md`, `docs/radio-parameters.md`, `docs/dev-log.md`.

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
