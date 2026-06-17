# TODO

## Current slice

Goal: Reorganize TUI command hints into categories and show shortcuts before full command names.

Done criteria:

- Group command hints into categories similar to key hints.
- Format aliases/shortcuts before canonical command names, e.g. `tu (tune)`.
- Preserve filtering, unique-command argument hints, aliases, and semicolon segment context.
- Update TUI harness tests and dev-log.

Test command: `python3 -m pytest tests/harness/test_tui.py && python3 -m pytest`

Live-radio needed: no; TUI rendering only.

Docs to update: `docs/dev-log.md`.

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
