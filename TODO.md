# TODO

## Current slice

Goal: Fix connected status and surface explicit busy-server messages.

Done criteria:

- Dashboard connected status shows yes while a live background operation is running.
- `status` command reports computed connected state when background operation is active.
- Detect Kiwi `MSG too_busy=<n>` and report a clear server-busy error.
- Detect Kiwi `MSG badp=1` as bad password or all no-password channels busy.
- Detect Kiwi `MSG down` as server down.
- Cover behavior with harness tests/fixtures.

Test command: `python3 -m pytest tests/harness tests/audio tests/protocol`

Live-radio needed: no; harness-first status/error work.

Docs to update: root `config.toml` if needed, `docs/roadmap.md`, `docs/user-guide.md`, `docs/dev-log.md`

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
