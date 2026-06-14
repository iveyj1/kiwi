# TODO

## Current slice

Goal: Add a strict offline replay transport for command/response fixture scripts.

Done criteria:

- Add a replay transport that consumes fixture events in order.
- Validate transmitted command text against `tx`/`cmd` fixture events.
- Return received MSG and binary payload events without network access.
- Cover successful SND setup/session replay and command mismatch failure with pytest.
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
