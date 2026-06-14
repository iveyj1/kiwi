# TODO

## Current slice

Goal: Push live play/record/capture toward usable live mode by allowing explicit sessions up to about 60 seconds.

Done criteria:

- Increase guarded live duration cap from 5 seconds to 60 seconds.
- Increase guarded live SND frame cap from 100 to 1500 frames.
- Keep default operations short unless the user explicitly requests longer values.
- Cover the new guardrail limits for capture, record, and playback with pytest.
- Update user docs and roadmap.

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
