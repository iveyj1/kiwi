# TODO

## Current slice

Goal: Add richer live status metrics and make the TUI refresh status periodically without requiring keypresses.

Done criteria:

- Publish sample rate, sequence gap count, ADC overflow, SND frame count, and latest RSSI/S-meter metrics from live playback/record/capture paths where available.
- Show sample rate, sequence gaps, ADC overflow, RSSI/S-meter, SND frames, operation result, and operation error in the TUI dashboard.
- Make the curses TUI redraw periodically so RSSI/status/error changes appear without keyboard input.
- Cover status metrics and dashboard rendering with pytest.

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
