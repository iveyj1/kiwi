# TODO

## Current slice

Goal: Measure the W/F bin center offset against a known-exact reference.

Done criteria:

- `kiwi-wf-sweep` steps the receive window past a reference tone and intersects one offset constraint per window position.
- Frames are grouped by reported `x_bin_server`, so the receiver may quantise `cf` freely.
- Analysis averages frames rather than max-holding, so a weak reference is not lost to noise peaks.
- Validation rejects a sweep too short to cross a bin boundary, a step too coarse to improve on the existing 0.133 bin bound, and a zoom too low to center the reference.
- `--analyse` re-reads a saved sweep with no network access.
- Harness tests recover a planted offset to one window position without a receiver.
- Live capture: a WWVB sweep at 60 kHz, zoom 9 or 10.
- Optional cross-check: a WWV sweep at 10 MHz, which places `start` several hundred times higher.
- `PROVISIONAL_BIN_CENTER_OFFSET` and `docs/kiwi-protocol.md` are updated from the measured result.

Test command: `python3 -m pytest tests/waterfall/ tests/harness/test_waterfall_sweep_cli.py && python3 -m pytest`

Live-radio needed: yes, but only after the harness tests pass. Short guarded sweeps against a local receiver; no generator use until `SET gen=` scope is known.

Docs to update: `docs/kiwi-protocol.md`, `docs/user-guide.md`, `docs/dev-log.md`.

## Done in previous slices

Goal: Reduce W/F bins to display columns so one frame renders as one row.

Done criteria:

- `waterfall_render.py` exposes a deterministic bin-to-column reduction with `max` and `mean` aggregation.
- Bucket boundaries cover every bin exactly once, with bucket sizes differing by at most one bin.
- `max` aggregation is the default so narrow carriers survive decimation.
- Reduction is a no-op when the requested column count is at least the bin count; the library never upsamples.
- ASCII row rendering accepts an optional column count without changing existing full-width behavior.
- `kiwi-wf-preview` and `kiwi-wf-live` default to the detected terminal width and accept `--columns`, where `--columns 0` restores one character per bin.
- `LiveWaterfallCaptureConfig` carries an explicit `ascii_columns` value so dry-run plans and capture metrics stay deterministic; terminal width is resolved in the CLI layer only.
- Harness tests cover reduction arithmetic, clamping, terminal-width defaulting, and rendering from the 1024-bin local fixture.
- `docs/waterfall-spec.md`, `docs/waterfall-rendering.md`, `docs/user-guide.md`, and `docs/dev-log.md` record the new display option.

Test command: `python3 -m pytest tests/harness/test_waterfall_render.py tests/harness/test_waterfall_preview.py tests/harness/test_live_waterfall_preview.py tests/harness/test_live_waterfall.py && python3 -m pytest`

Live-radio needed: no; rendering and CLI behavior only, using existing fixtures.

Docs to update: `docs/waterfall-spec.md`, `docs/waterfall-rendering.md`, `docs/user-guide.md`, `docs/dev-log.md`.

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

Goal: Support sub-Hz Kiwi tuning commands.

Done criteria:

- Add configurable Kiwi modulation command frequency precision.
- Preserve existing 3-decimal default command formatting unless configured otherwise.
- Root config enables 4-decimal command frequency formatting for local sub-Hz step testing.
- Active playback retune commands and live setup plans use configured command precision.
- Harness tests prove a sub-Hz step emits a sub-Hz `SET mod ... freq=` value.
- Update root `config.toml`, user docs, radio parameter docs, Kiwi protocol notes, and dev log.

Test command: `python3 -m pytest tests/protocol/test_commands.py tests/harness/test_config.py tests/harness/test_client_app.py tests/harness/test_tui.py && python3 -m pytest`

Live-radio needed: no; command encoding behavior only.

Docs to update: `docs/user-guide.md`, `docs/radio-parameters.md`, `docs/kiwi-protocol.md`, `docs/dev-log.md`.

## Next

- Explain the provisional `0.83` bin center offset in `WaterfallSpan`. Constancy in bins is settled by the zoom-11 capture, and the data admits only `0.762 < offset <= 0.895`, excluding both a half-bin (0.5) and a whole-bin (1.0) convention. Remaining question is the cause; identifying the receiver's FFT window is the likely next step.
- Confirm the `flags_x_zoom_server` bit layout beyond the low zoom bits; only `8` (zoom 8) and `0x40009` (zoom 9) have been observed.
- Show a frequency axis in the W/F previews now that bin/frequency mapping exists.
- Decide how `wf_cal=-13` should be applied to displayed dBm values.
- When ready for richer terminal display, implement the bookmarked `docs/terminal-waterfall-renderer.md` spec.
- Decide whether to integrate a compact waterfall pane into the curses TUI or keep standalone live preview first.

## Later

- Basic desktop client: connect, tune, mode, audio.
- Waterfall decode and rendering.
- Recording pipeline.
- MF/LF beacon detector.
- Long-integration/correlation analysis.
