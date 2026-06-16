# TODO

## Current slice

Goal: Add a deterministic fixed-scale ASCII waterfall row renderer.

Done criteria:

- Add renderer tests using the synthetic W/F fixture and known dBm values.
- Implement fixed-scale dBm-to-ramp mapping with clamp behavior.
- Implement a UI-independent ASCII row renderer for one `WaterfallFrame`.
- Update waterfall spec, roadmap, and dev-log.

Test command: `python3 -m pytest tests/harness/test_waterfall_render.py tests/protocol/test_waterfall.py && python3 -m pytest`

Live-radio needed: no; use synthetic fixture and parser/model tests.

Docs to update: `docs/waterfall-spec.md`, `docs/roadmap.md`, `docs/dev-log.md`.

## Next

- Add fixture-to-text preview command.
- Add W/F sequence gap tracking.
- Capture a short local W/F fixture only after parser/render harness coverage exists.

## Later

- Basic desktop client: connect, tune, mode, audio.
- Waterfall decode and rendering.
- Recording pipeline.
- MF/LF beacon detector.
- Long-integration/correlation analysis.
