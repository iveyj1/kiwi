# TODO

## Current slice

Goal: Clean preset/state ownership and receiver-register hints.

Done criteria:

- When explicit receiver presets exist, receiver prefix hints show those registers only and do not add fallback config receiver `0`.
- Full radio presets exclude config/state-owned fields: `allowed_receivers`, audio fade/mute settings, `receivers_restricted`, `user`, and `volume_percent`.
- Last state keeps `volume_percent`; missing last-state volume defaults to 10%.
- Update pwd `config.toml`, `presets.toml`, and local ignored `state.json` to the current layout.
- Update docs and harness tests.

Test command: `python3 -m pytest tests/harness/test_state_store.py tests/harness/test_tui.py && python3 -m pytest`

Live-radio needed: no; TUI/persistence only.

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
