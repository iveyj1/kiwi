# TODO

## Current slice

Goal: Improve TUI frequency/step display and harden repeated playback start.

Done criteria:

- Add `[display].frequency_decimals`, default `3`, for displayed kHz frequency/step precision.
- Display step pairs as fractional kHz to the same precision as frequency.
- Label AM/USB/LSB frequency as `Frequency`; label CW as `Center frequency`.
- In CW mode, show a separate radio frequency / CW offset line.
- Verify sub-Hz configured steps are represented when display precision is high enough.
- Repeating `:pb` while a background operation is already running reports an error instead of crashing TUI.
- Root `config.toml`, user docs, radio parameter docs, and dev log are updated.

Test command: `python3 -m pytest tests/harness/test_config.py tests/harness/test_client_app.py tests/harness/test_tui.py && python3 -m pytest`

Live-radio needed: no; TUI/display robustness only.

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
