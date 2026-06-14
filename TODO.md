# TODO

## Current slice

Goal: Deliver tune/mode/filter changes to active background playback sessions.

Done criteria:

- Add a command queue to the background operation worker.
- Wire live playback to drain queued control commands after initial SND setup.
- Queue `SET mod=...` when `tune`, `mode`, or `filter` changes while background playback is active.
- Show the queued/applied active command in the TUI dashboard response.
- Cover command queue behavior and active retune/mode/filter command generation with pytest.

Test command: `python3 -m pytest tests/harness tests/audio tests/protocol`

Live-radio needed: optional follow-up; harness first in this slice.

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
