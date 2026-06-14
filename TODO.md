# TODO

## Current slice

Goal: Build a guarded SND live capture CLI/tool without executing live receiver access.

Done criteria:

- Add a CLI entrypoint/module for short local SND capture.
- Enforce local receiver allowlist, short duration, frame cap, output overwrite guard, and explicit `--allow-live` requirement.
- Support `--dry-run` to print the planned URI and fixture-tested command sequence without connecting.
- Write live captures using the existing JSONL capture writer when explicitly run later.
- Keep live-radio testing deferred in this slice.

Test command: `python3 -m pytest tests/harness tests/protocol tests/audio`

Live-radio needed: no

Docs to update: `docs/harness.md`, `docs/dev-log.md`, `docs/user-guide.md`

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
