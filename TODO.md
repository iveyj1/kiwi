# TODO

## Current slice

Goal: add direct frequency entry to the interactive `kiwi-wf-terminal` viewer.

Done criteria:

- `f` enters a visible kHz frequency-entry mode.
- Accept decimal digits and one decimal point; Backspace edits, Esc cancels, and Enter applies.
- Applying a valid non-negative finite frequency tunes the primary SND session and recenters W/F at the current zoom.
- Preserve the exact entered frequency for SND command precision and move the cursor there when the recentered W/F span arrives.
- Invalid/empty input remains local and does not queue receiver commands.
- Add pure decoder/model and pseudo-terminal command-routing tests before implementation.
- Preserve existing cursor/audio/navigation controls and terminal restoration.
- Update user/rendering docs, run the full harness, and merge into `wf1`; no automatic live connection.

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
- Investigate whether received W/F cadence decreases with zoom or only presented redraw cadence changes.
- Evaluate an optional small bounded W/F jitter/playout buffer. Measure whether timed frame release smooths bursty arrival without excessive latency; explicitly test target depth, underflow/overflow, oldest-frame dropping, and clean shutdown while keeping network receive nonblocking.
- Preserve old waterfall history across zoom/recenter changes by remapping each row onto the new frequency scale, stretching/resampling overlap and filling uncovered frequencies with black, similar to the KiwiSDR web client.
- Advanced long-integration/correlation analysis after recording and detector harnesses mature.
