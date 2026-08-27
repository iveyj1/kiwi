# Terminal Waterfall Image Renderer Spec

## Purpose

Provide an optional raster-image terminal waterfall viewer for KiwiSDR W/F data. This should make live waterfall output easier to interpret than the current ASCII row preview while preserving the fixture-first parser/model/render separation.

The implementation in `src/kiwi_client/waterfall_raster.py` and `src/kiwi_client/waterfall_terminal.py` provides fixture and guarded live Kitty rendering, an adaptive frequency ruler, tuned/passband overlays, and a local keyboard-controlled source-bin cursor. Receiver pan/zoom, audio tuning coordination, and TUI integration remain future work.

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
  --terminal-columns 128 \
  --terminal-rows 30 \
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

Installed entry point:

```bash
kiwi-wf-terminal --fixture tests/fixtures/kiwi/local-wf-5000-zoom0.jsonl --backend kitty
```

Use `--force` only when the terminal supports Kitty graphics but does not advertise itself as Kitty, Ghostty, or WezTerm.

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
- Reuse one image id and placement id and update/replace them in place when new rows arrive.
- Use Kitty quiet mode (`q=2`) so acknowledgements are not echoed as input text.
- Disable placement cursor movement (`C=1`) so repeated updates do not add blank lines or scroll.
- Auto-fit to the terminal width and half-height unless explicit placement dimensions are supplied.
- Before the first placement, reserve the configured row rectangle and move back to its top-left anchor; otherwise a `C=1` image started from the shell's bottom line is clipped below the viewport until exit.
- Reserve space only once, update at the stable anchor, and restore the cursor below the image when viewing finishes.
- Render an adaptive terminal-text frequency ruler above the image when frame metadata is sufficient; use 1/2/5 major spacing, configurable width-aware density, precision derived from interval, and overlap rejection while keeping labels outside the 1024-bin raster.
- Draw tuned frequency, optional passband edges, and a source-bin cursor as deterministic white/orange/magenta raster columns after history color rendering, without modifying stored dBm rows.
- Reserve a status row above the ruler for cursor frequency, tuned offset, source-bin step, and concise local keyboard help.
- Decode cursor keys incrementally so split terminal escape sequences are handled; always restore cbreak-mode terminal settings on exit.
- Use asyncio readiness notification without changing `O_NONBLOCK` on the input descriptor, because shell stdin/stdout may share one open-file description and therefore shared file-status flags.
- Avoid flooding terminal output; throttle updates if needed.
- Provide clear error if Kitty support is unavailable.

### Sixel backend

Future optional backend. Similar model, different encoder/protocol.

## Data model

The reusable `WaterfallHistory` model provides the in-memory waterfall buffer:

```text
WaterfallHistory
  rows: fixed-height ring buffer of dBm rows
  width: number of bins per row
  max_rows: display height
  append(frame)
  rows(newest_at_top=..., pad_dbm=...) -> rectangular numeric row matrix
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
- a fixed deterministic initial colormap; named colormaps are future work

The initial implementation uses a small deterministic built-in palette and a dependency-free PNG encoder. This avoids matplotlib overhead and keeps exact RGB/PNG behavior harness-testable. A future named-colormap API can be added without changing the history model.

Scaling rules:

- Clamp values outside render range.
- Map low values to dark colors and high values to bright colors.
- Keep receiver-side `--min-db` / `--max-db` separate from local render scale.

## Live operation flow

```text
Live W/F capture loop
  -> parse W/F payload
  -> WaterfallFrame
  -> WaterfallHistory.append(frame)
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
- Whether future detailed ticks belong in terminal text, raster pixels, or a native GUI backend.

## Suggested implementation order

1. Done: add `WaterfallHistory` with fixture tests.
2. Done: add deterministic dBm-to-RGB rendering and PNG encoding.
3. Done: add Kitty escape encoder with pure byte tests.
4. Done: add fixture-backed `kiwi-wf-terminal --fixture ... --backend kitty`.
5. Done: add guarded live mode using fake WebSocket tests first.
6. Pending: run a short local visual test only after the full harness passes in an environment with pytest and a Kitty-capable terminal.
7. Done: add fixture-backed frequency mapping, adaptive labels, and a zoom-7 local AM regression capture.
8. Done: add tuned-frequency/passband overlays and persistent `[waterfall]` defaults with CLI precedence.
9. Done: isolate live terminal rendering from the network event loop, coalesce redraw requests, disable redundant WebSocket protocol pings, and report connection closure without a traceback.
10. Done: add a source-bin cursor, precise status readout, local keyboard movement/reset, and clean keyboard quit without transmitting receiver commands.
11. Pending: add fixture-tested receiver recenter/zoom commands, then coordinate selected tuning with the separate audio session.
