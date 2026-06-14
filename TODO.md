# TODO

## Current slice

Goal: Try recording offline by converting the captured SND fixture into a standard mono PCM WAV file.

Done criteria:

- Add a recording helper for uncompressed mono SND fixture audio.
- Use `MSG sample_rate` as WAV sample-rate source, rounded to integer Hz for the WAV header.
- Validate WAV channel count, sample width, frame rate, frame count, SND frame count, and sequence gaps with pytest.
- Produce a local WAV artifact from `tests/fixtures/kiwi/local-snd-5000-am-10khz.jsonl`.

Test command: `python3 -m pytest tests/audio tests/harness tests/protocol`

Live-radio needed: no

Docs to update: `docs/audio-pipeline.md`, `docs/user-guide.md`, `docs/dev-log.md`

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
