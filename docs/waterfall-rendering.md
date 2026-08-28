# Waterfall Rendering

## Purpose

Decode KiwiSDR waterfall frames into a deterministic display model and later a desktop renderer.

See [Waterfall display specification](waterfall-spec.md) for the current fixture-first implementation plan, parser/model boundaries, display options, and open protocol questions. Future terminal raster-image rendering is bookmarked in [Terminal Waterfall Image Renderer Spec](terminal-waterfall-renderer.md).

## Current observations

- The local fixture `tests/fixtures/kiwi/local-wf-5000-zoom0.jsonl` contains 2 rows x 1024 bins.
- Static PNG inspection via `tools/waterfall_image.py` works after `./setup-python` installs the `image` extra.
- Standalone live ASCII preview defaults to 50 rows / 60 seconds and supports local display scaling with `--render-min-db`, `--render-max-db`, and `--ramp` independent from receiver-side `--min-db` / `--max-db` commands.
- Bin-to-column reduction now runs before ramp mapping, so one 1024-bin frame renders as one terminal row instead of wrapping across several. Buckets use `i * bins // columns` edges, so every bin lands in exactly one bucket and bucket sizes differ by at most one bin. `max` aggregation is the default so a single-bin carrier survives decimation; `mean` is available for noise-floor viewing.
- Terminal width is resolved only in the CLI layer (`resolve_columns()` / `terminal_columns()`). `LiveWaterfallCaptureConfig.ascii_columns` carries an explicit count so capture plans and status metrics stay deterministic under test.
- Bin-to-frequency mapping is available via `WaterfallSpan` / `apply_span()`; see the W/F section of [Kiwi protocol notes](kiwi-protocol.md). The previews do not yet draw a frequency axis.
- A carrier near a bin boundary occupies two adjacent bins by FFT scalloping. Whether that renders as one character or two depends on where the display column boundary falls, so apparent carrier width changes with terminal width. This is expected; column reduction cannot split a single bin.
- Raw intensity mapping `sample - 255` gives plausible uncalibrated values for the fixture: about `-200..-25 dBm`, median near `-87 dBm`, with stable bright bins near the low-bin edge and around bins 529/538.
- The first bin is `-200 dBm` in both local rows; bin orientation and exact frequency mapping remain open until center/span/start metadata is incorporated.

- A colour half-block pane is integrated into the curses TUI via `waterfall_display.py` (model), `waterfall_palette.py` (xterm-256 ramp), and `waterfall_pane.py` (cells and drawing). Two frames per character row, 24 levels, fed from fixtures.
- Curses colour is limited to the terminal's 256-colour palette. `init_extended_pair` is unavailable in the local Python curses build, so 24-bit colour is not reachable from a curses pane even on a truecolor terminal. A future standalone renderer writing raw escapes could do better.
- A half-block cell needs one colour pair per (upper, lower) level combination, so N levels need `1 + N*N` pairs. The ceiling is 255, not what the terminal advertises: `curses.color_pair()` packs the pair number into the 8-bit `A_COLOR` field and anything above 255 wraps to `number & 0xFF`. Reaching the terminal's advertised 32767 would need `init_extended_pair`, absent from the local Python curses build. Hence 15 levels, 226 pairs.

## Questions to resolve

- Bin order
- Frequency span and center mapping
- Color mapping beyond fixed diagnostic scales
- Timing/update rate
- Zoom/span behavior

## Design constraints

- Keep waterfall protocol decoding separate from UI rendering.
- Make fixed input frames produce deterministic display rows.
- Use fixture tests for frame decode and mapping.
- The first waterfall view can be a separate lightweight window/process from any TUI. Do not force waterfall rendering into the TUI if a standalone view simplifies early development.
