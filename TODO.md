# TODO

## Current slice

Goal: Add background live playback worker and interactive stop/status support for the current TUI/client shell.

Done criteria:

- Add a framework-neutral background operation worker.
- Add cooperative stop support to live SND playback.
- Add `play-bg --allow-live [--null-sink]`, `stop`, and `operation-status` commands.
- Show background operation state in the TUI dashboard.
- Cover worker behavior, command behavior, and dashboard rendering with pytest.
- Keep retuning during active playback as desired-state-only for now.

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
