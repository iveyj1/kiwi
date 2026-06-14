# TODO

## Current slice

Goal: Add fixture-tested SND setup command encoders before any live receiver capture.

Done criteria:

- Add command encoder helpers for non-admin SND setup commands.
- Add a synthetic expected command sequence fixture.
- Cover auth, identity, mode/frequency, AGC, compression, and keepalive commands with pytest.
- Match the command fixture from generated encoder output.
- Keep live-radio testing deferred.

Test command: `python3 -m pytest tests/harness tests/protocol`

Live-radio needed: no

Docs to update: `docs/kiwi-protocol.md`, `docs/harness.md`, `docs/dev-log.md`

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
