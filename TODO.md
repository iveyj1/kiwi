# TODO

## Current slice

Goal: Waterfall fixture inspection and sequence semantics.

Done criteria:

- Generated static W/F PNG inspection path is usable from a fresh setup.
- `setup-python` installs the development, live, playback, and waterfall image dependencies needed to run the full harness on a new machine with Python already installed.
- Missing waterfall image libraries report a clear remediation command.
- The standalone live ASCII preview prints 50 rows by default.
- The standalone live ASCII preview can adjust local display scale separately from receiver-side W/F min/max dB settings.
- The local W/F fixture `tests/fixtures/kiwi/local-wf-5000-zoom0.jsonl` is inspected for plausible bin orientation/scaling.
- Repeated local W/F `seq=0` behavior is investigated before sequence tracking treats repeated zero as dropout.
- `docs/kiwi-protocol.md`, `docs/waterfall-rendering.md`, and `docs/dev-log.md` are updated if protocol/rendering conclusions change.

Test command: `python3 -m pytest`

Live-radio needed: not initially; use existing fixtures first. If more W/F frames are needed, perform a short guarded local-only capture after harness tests pass.

## Next

- Add frequency/bin mapping from local W/F metadata (`center_freq`, `bandwidth`, `wf_fft_size`, zoom/start).
- When ready for richer terminal display, implement the bookmarked `docs/terminal-waterfall-renderer.md` spec.
- Decide whether to integrate a compact waterfall pane into the curses TUI or keep standalone live preview first.

## Later

- Basic desktop client: connect, tune, mode, audio.
- Waterfall decode and rendering.
- Recording pipeline.
- MF/LF beacon detector.
- Long-integration/correlation analysis.
