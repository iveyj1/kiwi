# TODO

## Current slice

Goal: Advance Milestone 4 direct live-to-WAV recording and Milestone 5 playback as far as practical.

Done criteria:

- Add direct SND-to-WAV recording session logic that is covered by replay transport.
- Add a guarded `kiwi_client.live_record` CLI with dry-run and `--allow-live` gating.
- Add playback scaffolding with WAV chunking and a null audio sink for dry-run/test use.
- Add CLI entrypoints for direct recording and playback dry-run.
- Update roadmap and user docs with current milestone status and limitations.

Test command: `python3 -m pytest tests/audio tests/harness tests/protocol`

Live-radio needed: optional; if run, short local receiver only after harness passes.

Docs to update: `docs/roadmap.md`, `docs/audio-pipeline.md`, `docs/user-guide.md`, `docs/dev-log.md`

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
