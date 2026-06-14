# TODO

## Current slice

Goal: Get short guarded live SND playback working.

Done criteria:

- Add optional `sounddevice` sink behind the existing playback `AudioSink` interface.
- Add guarded live SND playback CLI with dry-run, null-sink, and explicit `--allow-live` modes.
- Cover live playback command/session flow with replay transport and `NullAudioSink`.
- Verify one short local null-sink live playback run.
- Verify one short local real audio output run if an output device is available.
- Update roadmap and user docs.

Test command: `python3 -m pytest tests/audio tests/harness tests/protocol`

Live-radio needed: yes, short local receiver only after harness passes.

Docs to update: `docs/roadmap.md`, `docs/audio-pipeline.md`, `docs/user-guide.md`, `docs/radio-lab.md`, `docs/dev-log.md`

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
