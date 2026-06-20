# TODO

## Current slice

Goal: Split durable config/presets from ephemeral TUI state.

Done criteria:

- Discover config path from explicit `--config`, `./config.toml`, `~/.config/kiwi-client/config.toml`, or built-in defaults.
- Add `[presets].file` config, resolving relative paths against the config directory.
- Store radio presets and receiver register presets in a TOML presets file.
- Keep `state.json` limited to ephemeral `last_state` only.
- Keep `[receivers].allowed` in config and avoid duplicating receivers.
- Update root `config.toml`, docs, and harness tests.

Test command: `python3 -m pytest tests/harness/test_config.py tests/harness/test_state_store.py tests/harness/test_tui.py && python3 -m pytest`

Live-radio needed: no; persistence/config only.

Docs to update: `docs/user-guide.md`, `docs/radio-parameters.md`, `docs/dev-log.md`, `docs/roadmap.md`.

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
