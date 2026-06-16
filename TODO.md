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

- Investigate W/F sequence semantics: local fixture repeated `seq=0` for two frames despite valid 1024-bin payloads.
- Add frequency/bin mapping from local W/F metadata (`center_freq`, `bandwidth`, `wf_fft_size`, zoom/start).
- Decide whether to integrate a compact waterfall pane into the curses TUI or keep standalone live preview first.

## Later

- Basic desktop client: connect, tune, mode, audio.
- Waterfall decode and rendering.
- Recording pipeline.
- MF/LF beacon detector.
- Long-integration/correlation analysis.
