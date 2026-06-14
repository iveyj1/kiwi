# TODO

## Current slice

Goal: Make fixture-to-WAV recording user-facing with a CLI.

Done criteria:

- Add a `kiwi_client.recorder` CLI entrypoint for converting an SND fixture to WAV.
- Add a project script entry for fixture-to-WAV conversion.
- Support JSON summary output for recording metadata.
- Cover the CLI with pytest using the live-captured 5000 kHz fixture.
- Produce/refresh the local WAV artifact via the CLI.

Test command: `python3 -m pytest tests/audio tests/harness tests/protocol`

Live-radio needed: no

Docs to update: `docs/user-guide.md`, `docs/dev-log.md`

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
