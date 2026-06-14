# TODO

## Current slice

Goal: Start Milestone 6 with a basic scriptable client control surface.

Done criteria:

- Add a small client controller/app state layer separate from protocol/transport/audio code.
- Support status, connect/disconnect state, receiver, tune, mode, filter, play-plan, record-plan, and capture-plan commands.
- Add a `kiwi-client` CLI that can run a command script and emit JSONL responses.
- Cover state transitions and generated operation plans with pytest.
- Keep live-radio testing deferred for this first Milestone 6 slice.

Test command: `python3 -m pytest tests/harness tests/audio tests/protocol`

Live-radio needed: no

Docs to update: `docs/roadmap.md`, `docs/user-guide.md`, `docs/dev-log.md`

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
