# Waterfall Rendering

## Purpose

Decode KiwiSDR waterfall frames into a deterministic display model and later a desktop renderer.

See [Waterfall display specification](waterfall-spec.md) for the current fixture-first implementation plan, parser/model boundaries, display options, and open protocol questions. Future terminal raster-image rendering is bookmarked in [Terminal Waterfall Image Renderer Spec](terminal-waterfall-renderer.md).

## Current observations

- The local fixture `tests/fixtures/kiwi/local-wf-5000-zoom0.jsonl` contains 2 rows x 1024 bins.
- Static PNG inspection via `tools/waterfall_image.py` works after `./setup-python` installs the `image` extra.
- Standalone live ASCII preview defaults to 50 rows / 60 seconds and supports local display scaling with `--render-min-db`, `--render-max-db`, and `--ramp` independent from receiver-side `--min-db` / `--max-db` commands.
- Raw intensity mapping `sample - 255` gives plausible uncalibrated values for the fixture: about `-200..-25 dBm`, median near `-87 dBm`, with stable bright bins near the low-bin edge and around bins 529/538.
- The first bin is `-200 dBm` in both local rows; bin orientation and exact frequency mapping remain open until center/span/start metadata is incorporated.

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
