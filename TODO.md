# TODO

## Current slice

Goal: Add W/F sequence gap tracking.

Done criteria:

- Add sequence tracker tests for in-order frames, gaps, out-of-order frames, and uint32 wraparound.
- Implement a UI-independent `WaterfallSequenceTracker` in the waterfall module.
- Update waterfall spec and dev-log.

Test command: `python3 -m pytest tests/protocol/test_waterfall.py && python3 -m pytest`

Live-radio needed: no; use synthetic frames.

Docs to update: `docs/waterfall-spec.md`, `docs/dev-log.md`.

## Next

- Retry short local W/F capture when a local receiver is available and not redirecting/busy.
- Update protocol notes with local fixture-backed W/F frame layout once a real W/F frame fixture is captured.
- Decide whether to integrate a compact waterfall pane into the curses TUI or keep standalone live preview first.

## Later

- Basic desktop client: connect, tune, mode, audio.
- Waterfall decode and rendering.
- Recording pipeline.
- MF/LF beacon detector.
- Long-integration/correlation analysis.
