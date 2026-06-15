# TODO

## Current slice

Goal: Add short configurable playback fade-in/fade-out around startup and receiver-switch stops.

Done criteria:

- Add configurable `[audio] startup_fade_in_ms` and `stop_fade_out_ms`.
- Live/replay SND playback fades in after the startup mute/drop window.
- Cooperative live playback stop fades out before exiting when frames are still arriving.
- TUI/client playback configs carry the settings.
- Cover behavior with harness tests.

Test command: `python3 -m pytest tests/harness/test_live_play.py tests/harness/test_config.py tests/harness/test_tui.py`

Live-radio needed: no; use replay fixture and harness tests first.

Docs to update: root `config.toml`, `docs/user-guide.md`, `docs/dev-log.md`, `docs/bumpless-transfer.md`.

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
