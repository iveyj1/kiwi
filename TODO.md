# TODO

## Current slice

Goal: validate the optimized waterfall redraw cadence in an attended session.

Implemented baseline:

- Each received W/F row is color-mapped once into bounded RGB history.
- Transient PNGs use fast level-1 compression.
- Refresh scheduling preserves draw-start cadence instead of adding idle time after every completed draw.
- One-bit coalescing, off-event-loop output, overlays, and numeric history remain intact.

Done criteria:

- Repeat the prior visual test at `rows=200`, `terminal_rows=20`, `refresh_hz=20`, and `speed=4`.
- Record CPU, approximate visible updates or bottom-to-top transition count, and whether motion is less jarring.
- If presentation remains substantially below receiver cadence, add measured receive/draw/encode/write timing diagnostics before another rendering change.

## Current status

Integration branch: `wf1`; `main` remains closed.

Latest completed baseline: combined Kitty raster waterfall plus paired primary SND audio, with cached RGB history and fast transient PNG encoding for improved redraw cadence. The full harness passes 283 tests.

Keep `config.toml` unchanged for now: it intentionally has `[live].allow_live = true`, unlimited live caps, `[receivers].restricted = false`, and the MISDR proxy allowlisted.

## Next slice candidates

### 1. Attended combined-viewer evaluation

Goal: verify normal interactive behavior now that the combined W/F+SND startup crash is fixed.

Done criteria:

- User or attended operator tests mute/audio toggle (`a`), Enter tune-to-cursor, `c` recenter, `+`/`-` zoom, and `q` shutdown.
- Use local receivers first unless explicitly evaluating the configured proxy.
- Record receiver, UTC/local time, frequency/mode/passband, W/F zoom/speed/interp, and observed behavior in `docs/dev-log.md` or `docs/radio-lab.md`.
- Add or update deterministic harness coverage before changing behavior.

### 2. Compact status/key-help refinement

Goal: improve `kiwi-wf-terminal` status readability if normal use shows truncation or clutter.

Done criteria:

- Add pure status-row/layout tests for narrow and medium terminal widths.
- Preserve current controls and audio/error visibility.
- Update `docs/user-guide.md` if displayed controls/status change.

### 3. Optional W/F timing diagnostics

Goal: instrument apparent temporal jumps only if they remain operationally problematic.

Done criteria:

- Add fixture/fake-runner diagnostics for receive cadence, coalesced redraw count, dropped redraw requests, render duration, and terminal-output duration.
- Keep diagnostics optional and low overhead.
- Do not change buffering policy until measurements justify it.

### 4. Product direction decision

Goal: decide whether waterfall remains a standalone companion or moves into another UI.

Options:

- Keep `kiwi-wf-terminal` as the primary W/F companion viewer.
- Integrate a compact waterfall pane into the curses TUI.
- Add a native desktop raster backend.

## Later

- Compressed SND ADPCM decode.
- Stereo/IQ SND decode.
- Longer controlled recording/playback with explicit gap/sample-rate policy.
- Beacon detector: start with synthetic carrier-present/absent, offset, noise, fading, weak-threshold, and false-positive fixtures before live captures.
- Advanced long-integration/correlation analysis after recording and detector harnesses mature.
