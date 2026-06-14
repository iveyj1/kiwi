# TODO

## Current slice

Goal: Add minimal MSG parsing and receiver/audio state context for fixture-based SND tests without live receiver access.

Done criteria:

- Add a synthetic SND session fixture with `MSG` state events followed by an SND frame.
- Parse `MSG` name/value parameters including flag-only and percent-escaped values.
- Track minimal receiver state: `sample_rate`, `audio_rate`, version, and bandwidth.
- Add harness coverage proving MSG state is applied before audio frame parsing.
- Keep live-radio testing deferred.

Test command: `python3 -m pytest tests/harness tests/protocol`

Live-radio needed: no

Docs to update: `docs/kiwi-protocol.md`, `docs/audio-pipeline.md`, `docs/dev-log.md`

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
