# TODO

## Current slice

Goal: Add an offline JSONL capture-writer shape for future SND live-to-fixture capture.

Done criteria:

- Add capture metadata structure for short SND captures.
- Add a JSONL capture writer for tx commands, rx MSG events, and rx binary payloads.
- Round-trip writer output through the existing fixture loader, MSG parser, receiver state, and SND parser.
- Keep live-radio testing deferred.

Test command: `python3 -m pytest tests/harness tests/protocol`

Live-radio needed: no

Docs to update: `docs/harness.md`, `docs/dev-log.md`

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
