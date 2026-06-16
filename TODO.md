# TODO

## Current slice

Goal: Add a test-rig matplotlib renderer for static W/F fixture images.

Done criteria:

- Add an offline tool under `tools/` that loads W/F JSONL fixtures into a dBm row matrix.
- Optionally render the matrix to PNG with matplotlib when available.
- Keep the tool out of production console scripts/core dependencies.
- Test the pure fixture-to-matrix data path with synthetic and local W/F fixtures.
- Update waterfall docs and dev-log with test-rig usage.

Test command: `python3 -m pytest tests/harness/test_waterfall_image_tool.py && python3 -m pytest`

Live-radio needed: no; use existing fixtures.

Docs to update: `docs/waterfall-spec.md`, `docs/user-guide.md`, `docs/dev-log.md`.

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
