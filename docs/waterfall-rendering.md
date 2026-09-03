# Waterfall Rendering

## Purpose

Decode KiwiSDR waterfall frames into a deterministic display model and later a desktop renderer.

See [Waterfall display specification](waterfall-spec.md) for the fixture-first parser/model boundaries and open protocol questions. The first standalone raster-image implementation is described in [Terminal Waterfall Image Renderer Spec](terminal-waterfall-renderer.md).

## Current observations

- The local fixture `tests/fixtures/kiwi/local-wf-5000-zoom0.jsonl` contains 2 rows x 1024 bins.
- Static PNG inspection via `tools/waterfall_image.py` works after `./setup-python` creates `.kiwi-venv` and installs the `image` extra; activate it with `source .kiwi-venv/bin/activate`.
- Standalone live ASCII preview defaults to 50 rows / 60 seconds and supports local display scaling with `--render-min-db`, `--render-max-db`, and `--ramp` independent from receiver-side `--min-db` / `--max-db` commands.
- `src/kiwi_client/waterfall_raster.py` now provides a fixed-height numeric history, deterministic RGB mapping, and dependency-free PNG encoding.
- `kiwi-wf-terminal` renders fixture or guarded live W/F frames as a raster image using Kitty graphics. The source image keeps all 1024 bins; default placement uses the full terminal width and half its height, with explicit cell-dimension overrides available.
- Kitty updates suppress terminal acknowledgements (`q=2`), prevent cursor movement (`C=1`), and reuse one placement id so live refreshes do not echo protocol text or scroll the display.
- The backend reserves the placement's terminal rows once, returns to a stable top-left anchor for live drawing, and restores the cursor below the image at shutdown. This prevents a fixed-cursor image from remaining clipped below the command line until the program exits.
- Live capture exposes parsed `WaterfallFrame` callbacks so raster rendering no longer needs to consume the ASCII status field.
- Kiwi `SET interp` is categorical, not a smoothing-strength control: `0..4` are max/min/last/drop/CMA FFT-bin reduction and `10..14` add CIC compensation. Default `13` is drop+CIC and is already the drop-sampling choice. Remaining visible spatial smoothing is primarily terminal image scaling.
- W/F MSG metadata and frame coordinates now populate start, center, span, and bin-width fields. `kiwi-wf-terminal` displays a text frequency ruler above the raster without reducing its 1024-bin source width.
- The ruler chooses major intervals from 1/2/5 × powers of ten, adapts its target count to terminal width, derives decimals from interval size, preserves mapped edges, and rejects overlapping interior labels.
- A local zoom-7 fixture centered near 855 kHz maps known 760 and 950 kHz AM carriers to within one 228.9 Hz bin, confirming nonzero-zoom mapping and left-to-right orientation.
- Renderer-side overlays draw a white tuned-frequency column, optional orange passband-edge columns, and a magenta local cursor column on a raster copy. History/model values remain unchanged, markers outside the mapped span are omitted, and passband order is validated.
- `WaterfallCursor` keeps exact selected frequency independently from source bins, snaps movement to zero-anchored configured frequency steps, clamps to the mapped span, and preserves frequency across resolution/context changes. The magenta marker projects selection onto the nearest raster column.
- The Kitty backend reserves a cursor status row above the adaptive ruler. It reports precise cursor frequency, tuned-frequency offset, and bin-width step; updates are emitted by the existing coalescing renderer.
- `[waterfall]` config persists standalone center/zoom, history/terminal rows, render range, speed, refresh rate, interpolation, label density, and overlay defaults; explicit CLI options win.
- Live frame parsing/history updates remain on the asyncio network path, while raster snapshot assembly, PNG encoding, and terminal writes run through one worker-thread renderer. Numeric dBm history is retained for model/inspection use, while a parallel bounded RGB history converts each received row once instead of recoloring the full history on every redraw. Transient terminal PNGs use fast level-1 compression. A one-bit redraw event coalesces requests: if output blocks while the terminal is unfocused, there is at most one current-state redraw pending rather than one encoded image per received frame.
- The redraw limiter schedules draw starts at the requested cadence. Render time no longer adds another complete refresh interval after every draw; if a draw overruns its deadline, one latest-state redraw may start immediately. `refresh_hz` remains a cap rather than a guarantee, and values above the receiver's reported `wf_fps` do not create intermediate radio frames.
- Because history continues while output is blocked, returning to a slow terminal can legitimately show one jump to current time. This is frame dropping at the display boundary, not a receive backlog being replayed.
- Raw intensity mapping `sample - 255` gives plausible uncalibrated values for the fixture: about `-200..-25 dBm`, median near `-87 dBm`, with stable bright bins near the low-bin edge and around bins 529/538.
- The first bin is `-200 dBm` in both local rows; bin orientation and exact frequency mapping remain open until center/span/start metadata is incorporated.

## Questions to resolve

- Confirm bin order and nonzero-zoom mapping with a captured local fixture
- Color mapping beyond fixed diagnostic scales
- Measure achieved draw/presentation cadence separately from requested refresh and receiver frame cadence if visible jumps remain problematic.
- Zoom/span behavior

## Design constraints

- Keep waterfall protocol decoding separate from UI rendering.
- Make fixed input frames produce deterministic display rows.
- Use fixture tests for frame decode and mapping.
- The first waterfall view can be a separate lightweight window/process from any TUI. Do not force waterfall rendering into the TUI if a standalone view simplifies early development.
