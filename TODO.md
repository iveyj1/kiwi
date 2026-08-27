# TODO

## Current slice

Goal: none active. The waterfall display and bin-mapping slice is complete.

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

- Parked: explain why the W/F bin center offset is not constant across window positions. Live WWVB and WWV sweeps both show peak transitions 35 window positions apart where the model requires 32, and a per-position offset range of 1.062 bins, which no constant can produce. Both references agree to 0.003 bins despite a 300x difference in `start`, so it depends on window position rather than frequency. Bin width and `unit_hz` are each independently confirmed, which makes the discrepancy genuinely puzzling; the likely answer is that the passband does not move by exactly one `unit_hz` per reported `x_bin_server` count. Needs the KiwiSDR BeagleBone/DSP sources, not more black-box captures. Evidence in `docs/evidence/`, details in `docs/kiwi-protocol.md`.
  Likely permanent. The waterfall is a visualization path; accurate frequency measurement belongs to the SND audio stream, which keeps full-resolution PCM and phase and reports its own `sample_rate`. That makes the offset a display concern only, and `0.83` already puts every measured carrier on the correct bin.
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
