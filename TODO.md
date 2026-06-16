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

- Add fixture-to-text preview command. (Done)
- Capture a short local W/F fixture only after parser/render harness coverage exists.

## Later

- Basic desktop client: connect, tune, mode, audio.
- Waterfall decode and rendering.
- Recording pipeline.
- MF/LF beacon detector.
- Long-integration/correlation analysis.
