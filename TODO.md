# TODO

## Current slice

Goal: Add and maintain a high-level roadmap document.

Done criteria:

- Create `docs/roadmap.md` with milestone statuses and next recommended capability.
- Capture completed SND harness, guarded capture, and offline WAV recording milestones.
- Capture planned direct live-to-WAV, playback, UI, waterfall, detector, and weak-signal milestones.
- Link the roadmap from project documentation.
- Establish that roadmap should be updated as capabilities change.

Test command: `python3 -m pytest`

Live-radio needed: no

Docs to update: `docs/roadmap.md`, `docs/project-brief.md`, `docs/dev-log.md`

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
