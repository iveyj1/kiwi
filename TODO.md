# TODO

## Current slice

Goal: Add fixture-based SND sequence/dropout and ADC overflow handling before live capture.

Done criteria:

- Add a synthetic multi-frame SND fixture with a sequence gap.
- Add an audio-layer SND sequence tracker with uint32 wraparound handling.
- Detect missing frames and out-of-order frames.
- Expose ADC overflow flag status from decoded SND frames.
- Keep live-radio testing deferred.

Test command: `python3 -m pytest tests/audio tests/harness tests/protocol`

Live-radio needed: no

Docs to update: `docs/audio-pipeline.md`, `docs/kiwi-protocol.md`, `docs/dev-log.md`

## Next

- Inspect `kiwiclient/` and identify SND/audio connection path.
- Define fixture format for KiwiSDR control and stream messages.
- Add first parser test using synthetic or captured SND data.
- Add first local live-radio capture only after the harness path exists.

## Later

- Basic desktop client: connect, tune, mode, audio.
- Waterfall decode and rendering.
- Recording pipeline.
- MF/LF beacon detector.
- Long-integration/correlation analysis.
