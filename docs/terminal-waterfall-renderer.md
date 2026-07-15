# Terminal Waterfall Image Renderer Spec

## Purpose

Provide an optional raster-image terminal waterfall viewer for KiwiSDR W/F data. This should make live waterfall output easier to interpret than the current ASCII row preview while preserving the fixture-first parser/model/render separation.

This is bookmarked future work, not the current implementation target.

## Goals

- Display live or fixture-backed W/F frames as an image inside capable terminals.
- Support Kitty graphics protocol first, with room for Sixel later.
- Reuse existing W/F parsing, scaling, and capture code.
- Keep terminal graphics optional; ASCII and PNG workflows must continue to work everywhere.
- Make rendering testable without a live receiver or a specific terminal.

## Non-goals

- Do not require Kitty/Sixel support for normal project use.
- Do not bury W/F protocol parsing inside terminal UI code.
- Do not couple this directly to curses TUI lifecycle at first.
- Do not implement a full GUI or browser-like Kiwi waterfall.

## Proposed command

Initial standalone experimental command:

```bash
kiwi-wf-terminal --allow-live \
  --host 10.0.0.40 \
  --backend kitty \
  --rows 100 \
  --width 1024 \
  --render-min-db -100 \
  --render-max-db -40
```

Dry-run/no-network mode:

```bash
kiwi-wf-terminal --dry-run --host 10.0.0.40 --backend kitty
```

Fixture preview mode:

```bash
kiwi-wf-terminal --fixture tests/fixtures/kiwi/local-wf-5000-zoom0.jsonl --backend kitty
```

## Renderer backends

### ASCII backend

Existing row renderer remains the baseline fallback.

### PNG/file backend

Existing `tools/waterfall_image.py` remains the offline inspection path.

### Kitty backend

Emit Kitty graphics protocol escape sequences to draw/update a raster image.

Requirements:

- Detect or require capable terminal via `TERM`, `KITTY_WINDOW_ID`, or explicit `--force`.
- Encode image data as PNG bytes, then base64 chunks for Kitty protocol.
- Reuse one image id and update/replace it in place when new rows arrive.
- Avoid flooding terminal output; throttle updates if needed.
- Provide clear error if Kitty support is unavailable.

### Sixel backend

Future optional backend. Similar model, different encoder/protocol.

## Data model

Add a reusable in-memory waterfall image buffer:

```text
WaterfallImageBuffer
  rows: fixed-height ring buffer of calibrated dBm rows
  width: number of bins per row
  max_rows: display height
  append(frame)
  matrix() -> rectangular row matrix, oldest-to-newest or newest-to-oldest by option
```

Behavior:

- First frame establishes bin width unless width is explicitly configured.
- Frames with mismatched width raise or are resampled only if a later explicit resampling feature is added.
- Buffer stores numeric dBm/intensity values, not terminal-specific pixels.
- Orientation must be configurable:
  - newest at bottom, conventional waterfall image
  - newest at top, packet/log style

## Color/scaling model

Use the same local display scaling concepts already added for ASCII preview:

- `--render-min-db`
- `--render-max-db`
- optional colormap name

Initial implementation options:

1. Use Pillow directly to map dBm rows to RGB pixels.
2. Use matplotlib colormaps only for quick implementation.

Preference: use a small Pillow/numpy-based mapper if this becomes production code, to avoid matplotlib overhead in live preview.

Scaling rules:

- Clamp values outside render range.
- Map low values to dark colors and high values to bright colors.
- Keep receiver-side `--min-db` / `--max-db` separate from local render scale.

## Live operation flow

```text
Live W/F capture loop
  -> parse W/F payload
  -> WaterfallFrame
  -> WaterfallImageBuffer.append(frame)
  -> render buffer to PNG bytes
  -> terminal backend update image
```

The live viewer should reuse guarded W/F capture/session logic:

- local receiver allowlist by default,
- `--allow-live` required,
- duration/frame caps,
- no admin commands,
- no reconnect loop.

## Test strategy

Harness-first tests:

1. Buffer tests:
   - append one frame,
   - append more than max rows,
   - reject mismatched width,
   - orientation oldest/newest behavior.

2. Color mapping tests:
   - known dBm values map to deterministic RGB values,
   - clamp low/high values,
   - render range validation.

3. Kitty encoder tests:
   - PNG bytes are base64 chunked correctly,
   - escape sequence includes image id/update fields,
   - no terminal required.

4. CLI tests:
   - dry-run plan,
   - fixture mode emits expected backend calls via fake backend,
   - live mode uses fake websocket and fake terminal backend.

Do not require a Kitty terminal in automated tests.

## Open questions

- Whether to render every incoming frame or update terminal image at a lower FPS.
- Best default row count for readability and terminal size.
- Whether to depend on Pillow/numpy or continue using matplotlib for first prototype.
- Whether terminal image viewer should later integrate into curses TUI or remain a separate companion command.
- How to map frequency/bin labels into terminal graphics without clutter.

## Suggested implementation order

1. Add `WaterfallImageBuffer` with fixture tests.
2. Add deterministic dBm-to-RGB image renderer returning PNG bytes.
3. Add Kitty escape encoder with pure string/bytes tests.
4. Add fixture-backed `kiwi-wf-terminal --fixture ... --backend kitty` prototype.
5. Add guarded live mode using fake websocket tests first.
6. Try short local live preview only after all harness tests pass.
