# TODO

## Current slice

Goal: Continue Milestone 6 by executing guarded play/record/capture functions from the scriptable client shell.

Done criteria:

- Add executable `play`, `record`, and `capture` commands to `kiwi-client`.
- Require explicit `--allow-live` for executable live operations while preserving existing `*-plan` commands.
- Support `play --null-sink`, `record --overwrite`, and `capture --overwrite` options.
- Keep operation execution dependency-injected so tests use fake operations and avoid live radio/audio hardware.
- Cover command execution and safety refusal with pytest.

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
