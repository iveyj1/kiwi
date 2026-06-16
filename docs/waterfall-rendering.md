# Waterfall Rendering

## Purpose

Decode KiwiSDR waterfall frames into a deterministic display model and later a desktop renderer.

See [Waterfall display specification](waterfall-spec.md) for the current fixture-first implementation plan, parser/model boundaries, display options, and open protocol questions.

## Questions to resolve

- Frame dimensions
- Bin order
- Frequency span and center mapping
- Intensity scaling
- Color mapping
- Timing/update rate
- Zoom/span behavior

## Design constraints

- Keep waterfall protocol decoding separate from UI rendering.
- Make fixed input frames produce deterministic display rows.
- Use fixture tests for frame decode and mapping.
- The first waterfall view can be a separate lightweight window/process from any TUI. Do not force waterfall rendering into the TUI if a standalone view simplifies early development.
