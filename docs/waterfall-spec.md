# Waterfall display specification

## Purpose

Define the harness-first plan for decoding and displaying KiwiSDR waterfall data without coupling protocol parsing to the TUI or any future desktop renderer.

The first goal is not a polished live display. The first goal is a deterministic waterfall parser/model and offline renderer that can be tested from synthetic and captured fixtures.

## Evidence consulted

Local reference code:

- `kiwiclient/kiwi/client.py`
- `kiwiclient/kiwirecorder.py`
- `kiwiclient/kiwiwfrecorder.py`
- `kiwiclient/microkiwi_waterfall.py`

Important reference observations, not yet locally fixture-verified in this project:

- Waterfall uses WebSocket stream type `W/F`.
- WebSocket binary messages use a 3-byte ASCII tag, like `SND` and `MSG`.
- `kiwiclient/kiwi/client.py` parses `W/F` frame bodies as:
  - `x_bin_server`: uint32 little-endian
  - `flags_x_zoom_server`: uint32 little-endian
  - `seq`: uint32 little-endian
  - payload bytes after the 12-byte body header
- Because the WebSocket message includes the 3-byte `W/F` tag and there appears to be one separator/flag byte before the 12-byte body header, simple examples skip 16 bytes total before raw uncompressed bins.
- Reference default bin count is `WF_BINS = 1024`.
- Reference setup commands include:
  - `SET auth t=kiwi p=`
  - `SET zoom=<zoom> cf=<center_khz>` for newer Kiwi versions
  - older fallback `SET zoom=<zoom> start=<counter>`
  - `SET maxdb=<dB> mindb=<dB>`
  - `SET wf_speed=<1..4>`
  - `SET wf_comp=<0|1>`
  - `SET interp=<value>`
- Reference code commonly starts with uncompressed waterfall data: `SET wf_comp=0`.
- Reference code maps raw byte samples to approximate dBm with `dBm = sample - 255` before applying waterfall calibration.
- Reference default or compatibility waterfall calibration is often `wf_cal = -13` dB.
- Reference span mapping uses `span_khz = MAX_FREQ / 2**zoom` and bin width `span_khz / WF_BINS`.

These facts must be promoted to fixture-backed project facts only after synthetic and local captured W/F fixtures cover them.

## Architecture

Keep the waterfall pipeline independent from audio playback and UI rendering:

```text
Waterfall transport / replay fixture
    -> W/F protocol parser
    -> WaterfallFrame model
    -> WaterfallHistory / scaling model
    -> renderer adapter
        -> terminal preview
        -> PNG/image output
        -> future TUI/GUI pane
```

The parser and model must be usable without curses, sounddevice, or network access.

## Proposed modules

Initial implementation can use these modules:

```text
src/kiwi_client/waterfall.py
    WaterfallFrame dataclass
    parse_waterfall_frame(...)
    raw_sample_to_dbm(...)
    frequency mapping helpers

src/kiwi_client/waterfall_render.py
    deterministic intensity scaling
    ASCII/ANSI preview rows
    optional PNG export if dependency policy allows it later

src/kiwi_client/live_waterfall.py
    guarded live W/F capture/view entrypoint, later only
```

Tests should begin with:

```text
tests/protocol/test_waterfall.py
tests/harness/test_waterfall_render.py
tests/fixtures/kiwi/wf-basic.jsonl
```

## Data model

Suggested first frame model:

```python
@dataclass(frozen=True)
class WaterfallFrame:
    sequence: int
    bins: tuple[int, ...]           # raw uint8 bins, normally 1024
    dbm: tuple[int, ...]            # deterministic raw-to-dBm mapping
    center_khz: float | None
    span_khz: float | None
    start_khz: float | None
    bin_width_hz: float | None
    x_bin_server: int | None
    flags_x_zoom_server: int | None
    raw_flags: int | None
```

The first parser can make frequency fields optional so protocol parsing is testable before live setup metadata is complete.

## Fixture format

Use the existing JSONL event format:

```json
{"t":0.000,"dir":"tx","stream":"wf","type":"cmd","text":"SET auth t=kiwi p="}
{"t":0.010,"dir":"tx","stream":"wf","type":"cmd","text":"SET zoom=0 cf=15000"}
{"t":0.050,"dir":"rx","stream":"wf","type":"binary","encoding":"base64","data":"..."}
```

Synthetic fixture `wf-basic.jsonl` should include:

- one uncompressed W/F frame
- known sequence number
- known `x_bin_server` and `flags_x_zoom_server`
- a short or full-width deterministic bin vector
- expected dBm conversion for selected bins

Keep ordinary regression fixtures small. If a full 1024-bin frame is too noisy for review, use one synthetic unit fixture at parser level and one compact JSON fixture with base64 payload.

## Parser phase

Implemented first parser scope in `src/kiwi_client/waterfall.py`:

- Accept WebSocket binary payload beginning with `b"W/F"`.
- Skip the stream tag and read the following stream separator/flags byte as `raw_flags`.
- Decode the 12-byte W/F body header as little-endian uint32 fields.
- For `wf_comp=0`, expose remaining bytes as unsigned raw bins.
- Convert raw bin values to approximate uncalibrated dBm with `sample - 255`.

Also implemented:

- `WaterfallSequenceTracker` tracks in-order frames, gaps, out-of-order frames, and uint32 wraparound using the same philosophy as SND sequence tracking.

Explicitly out of first scope:

- Compressed W/F decode.
- Full color rendering parity with Kiwi web UI.
- Live capture.
- Multi-stream audio + waterfall lifecycle integration.

## Rendering phase

Begin with deterministic offline rendering.

Implemented first renderer in `src/kiwi_client/waterfall_render.py`:

1. ASCII grayscale row renderer using a fixed ramp:

   ```text
    .:-=+*#%@
   ```

2. Fixed-scale dBm-to-ramp mapping with clamp behavior.

Implemented user-visible offline preview:

- `python3 -m kiwi_client.waterfall_preview tests/fixtures/kiwi/wf-basic.jsonl`
- console script: `kiwi-wf-preview`

Recommended next renderers:

1. Optional ANSI 256-color terminal preview after ASCII tests exist.
3. PNG export later if dependency policy is acceptable or if using only optional dependencies.

Deterministic scaling modes:

- fixed min/max dBm, e.g. `mindb=-110`, `maxdb=0`
- no per-frame auto-scaling in regression tests
- clamp before mapping to intensity/color

Avoid rolling/auto scaling in first tests because it makes output harder to assert.

## Display options

### TUI pane

Pros:

- Fits current curses app.
- Works over SSH.
- Useful with existing keymaps/status.

Cons:

- Limited color and resolution.
- Terminal performance varies.
- Layout becomes harder once audio/session status grows.

Use after parser/model/offline renderer exist.

### Standalone terminal preview

Pros:

- Simple harness target.
- Easier than integrating with current TUI.
- Can read fixtures or stdin.

Cons:

- Not yet a full interactive client.

Good first user-visible waterfall view.

### PNG/image renderer

A test-rig matplotlib renderer exists at `tools/waterfall_image.py`. It is intentionally outside the production package and console scripts. It loads W/F JSONL fixtures into a dBm row matrix and, when matplotlib is available, writes a static PNG.

Example:

```bash
PYTHONPATH=src python3 tools/waterfall_image.py \
  tests/fixtures/kiwi/local-wf-5000-zoom0.jsonl \
  artifacts/local-wf-5000-zoom0.png \
  --summary \
  --title "Local W/F 5000 kHz zoom 0"
```

Pros:

- Good visual inspection artifact.
- Easy to inspect and compare manually.
- Renderer independent from terminal constraints.

Cons:

- Requires optional local matplotlib installation.
- Not production code and not interactive.

### Future GUI/browser display

Pros:

- Best long-term rendering quality.
- Better pan/zoom/mouse interaction.

Cons:

- Larger framework and packaging decision.
- Should not precede parser/model confidence.

## Live waterfall considerations

Guarded W/F capture is implemented as `python3 -m kiwi_client.live_waterfall` / `kiwi-wf-capture`. Standalone guarded ASCII live preview is implemented as `python3 -m kiwi_client.live_waterfall_preview` / `kiwi-wf-live`. Live work should still wait until parser and offline renderer tests pass.

Before live capture:

- State the short test goal.
- Use local receivers only unless explicitly requested otherwise.
- Avoid reconnect loops.
- Keep duration short.
- Capture useful W/F frames as fixtures.

Initial live W/F capture uses safe, non-admin setup commands only:

```text
SET auth t=kiwi p=
SET zoom=<zoom> cf=<center_khz>
SET maxdb=<maxdb> mindb=<mindb>
SET wf_speed=<1..4>
SET wf_comp=0
SET interp=<interp>
SET keepalive
```

Exact command order and required MSG handling must be verified with local fixture capture.

## Relationship to current session architecture

The current background worker supports one operation at a time. Live audio plus live waterfall simultaneously will likely require one of these approaches:

1. Add waterfall as a separate standalone process/view first.
2. Add a multi-operation/session manager capable of independent SND and W/F workers.
3. Treat waterfall display as mutually exclusive with playback initially.

Recommendation: start with standalone offline and then standalone live W/F view before integrating live waterfall into the existing TUI playback session.

## Open questions

- Confirm exact stream byte layout from local receiver fixtures: 3-byte tag, one separator/flag byte, 12-byte W/F header, payload.
- Confirm whether local receivers require `SET interp` and preferred default.
- Confirm `flags_x_zoom_server` bit layout.
- Confirm `x_bin_server` meaning and whether it is needed for display frequency mapping.
- Confirm default MAX_FREQ used by target receivers for span calculations.
- Decide whether first display uses raw dBm, calibrated dBm, or normalized intensity.
- Decide dependency policy for PNG rendering.
- Decide when live audio and live waterfall should be allowed concurrently.

## Recommended implementation order

1. Add synthetic W/F frame fixture.
2. Add `parse_waterfall_frame()` tests for uncompressed W/F.
3. Add `WaterfallFrame` and raw-to-dBm conversion.
4. Add fixed-scale ASCII renderer tests.
5. Add fixture-to-text preview command.
6. Capture a short local W/F fixture.
7. Update `docs/kiwi-protocol.md` with fixture-backed W/F facts.
8. Add a standalone live W/F preview.
9. Decide whether to integrate a compact pane into the curses TUI or move toward a richer renderer.
