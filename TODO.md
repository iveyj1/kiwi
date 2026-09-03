# TODO

## Current slice

Goal: render more intermediate waterfall states without increasing receiver traffic or allowing an unbounded redraw backlog.

Observed behavior: at `rows=500`, `terminal_rows=40`, `refresh_hz=20`, and receiver `speed=4`, the viewer uses about 40% CPU but visibly redraws only around four times per second. Each update advances enough history to look jarring.

Done criteria:

- Add deterministic raster tests before implementation.
- Avoid rebuilding RGB values for every retained history row on every redraw; convert each received row once and retain a bounded RGB history alongside numeric history.
- Use a faster deterministic PNG compression level suitable for transient terminal frames.
- Make the redraw cap apply to draw start cadence rather than adding a full refresh interval after each completed draw.
- Preserve one-bit coalescing, off-event-loop rendering, overlays, fixture output, and bounded memory.
- Run targeted waterfall tests and the full harness; do not connect externally automatically.

## Current status

Integration branch: `feature/wf-render-cadence` from `wf1`; `main` remains closed.

Latest completed baseline: combined Kitty raster waterfall plus paired primary SND audio. User validation confirmed proxy W/F+SND operation after using one shared Kiwi session timestamp and opening/authenticating SND before paired W/F.

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
