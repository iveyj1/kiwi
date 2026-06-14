# TODO

## Current slice

Goal: Add interactive AGC controls and clarify volume behavior.

Done criteria:

- Confirm local reference support for `SET agc=...`; do not invent unverified radio-side volume command.
- Add AGC state to the client model.
- Add commands for AGC on/off, hang, threshold, slope, decay, and manual gain.
- Queue AGC command changes to active background playback sessions.
- Cover AGC command behavior with harness tests.
- Update docs to explain volume controls local system output and AGC gain is the verified Kiwi receiver-side gain control.

Test command: `python3 -m pytest tests/harness tests/audio tests/protocol`

Live-radio needed: no; harness-first command/control work.

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
