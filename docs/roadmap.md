# Roadmap

This roadmap tracks high-level capabilities and should be updated as milestones are completed or priorities change.

Status key:

- **Done**: implemented, tested, and documented enough for current scope.
- **In progress**: active foundation exists but capability is not complete.
- **Planned**: intended but not started.
- **Deferred**: explicitly postponed.

## Current position

The project has completed the first SND audio harness, local capture, and offline recording milestone.

Current verified baseline:

- Offline tests pass: `python3 -m pytest`.
- Local receiver fixture captured from `10.0.0.40:8073` at 5000 kHz AM, 10 kHz bandwidth.
- Captured uncompressed mono SND fixture can be converted to a standard WAV file.

## Milestone 1 — SND protocol and harness foundation

Status: **Done for uncompressed mono SND**

Capabilities:

- JSONL fixture format.
- Fixture loader and writer.
- Offline replay transport.
- MSG parser.
- Uncompressed mono SND parser.
- Receiver state model for sample rate, audio rate, version, and bandwidth.
- Command encoders for initial SND setup.
- Sequence gap/dropout tracking.
- ADC overflow flag exposure.

Evidence:

- `tests/fixtures/kiwi/snd-basic.jsonl`
- `tests/fixtures/kiwi/snd-session-basic.jsonl`
- `tests/fixtures/kiwi/snd-sequence-gap.jsonl`
- `tests/protocol/`
- `tests/harness/`
- `tests/audio/`

Remaining follow-ons:

- Compressed SND ADPCM decode.
- Stereo/IQ SND decode.
- More malformed frame coverage.

## Milestone 2 — Guarded local SND capture

Status: **Done for short local uncompressed mono capture**

Capabilities:

- Guarded live capture CLI.
- Local receiver allowlist.
- Explicit `--allow-live` requirement.
- Dry-run mode.
- Short duration and frame caps.
- JSONL capture output.
- Regression fixture from local receiver.

Evidence:

- `src/kiwi_client/live_capture.py`
- `tests/fixtures/kiwi/local-snd-5000-am-10khz.jsonl`
- `tests/harness/test_local_snd_capture.py`
- `docs/radio-lab.md`

Known observations:

- Live Kiwi MSG frames can arrive as binary WebSocket payloads beginning with `MSG`.
- Tested local receiver reported sample rate near, but not exactly, 12000 Hz.

Remaining follow-ons:

- Better busy/max-user fixture and error handling.
- More capture presets.
- Longer controlled captures after buffering/recording logic matures.

## Milestone 3 — Offline WAV recording

Status: **Done for fixture-to-WAV, uncompressed mono**

Capabilities:

- Convert uncompressed mono SND JSONL fixtures to WAV.
- Standard mono 16-bit PCM output.
- Uses `MSG sample_rate`, rounded to integer Hz for WAV header.
- Reports recording summary.
- CLI entrypoint for fixture-to-WAV conversion.

Evidence:

- `src/kiwi_client/recorder.py`
- `tests/audio/test_wav_recorder.py`
- Local generated artifact: `recordings/local-snd-5000-am-10khz.wav` (ignored by git)

Remaining follow-ons:

- Direct live-to-WAV recording.
- Gap handling policy in written WAV files.
- Recording metadata sidecar.
- User-configurable output naming.

## Milestone 4 — Direct live-to-WAV recording

Status: **Planned / recommended next**

Goal:

Capture a short local receiver session and write WAV directly, while optionally preserving JSONL fixture data.

Done criteria:

- Harness coverage for live-recording pipeline using replay transport.
- Guarded CLI mode for short live WAV recording.
- No admin commands or reconnect loop.
- Output WAV validates with Python `wave`.
- Optional JSONL sidecar or fixture capture remains available for regression.

Risks/questions:

- Whether to write silence for sequence gaps or only report them.
- How to handle receiver sample-rate drift in longer WAV recordings.
- Whether live recording should always save a JSONL fixture sidecar.

## Milestone 5 — Basic audio playback

Status: **Planned**

Goal:

Play decoded SND audio locally.

Suggested order:

1. Fixture WAV playback or fixture buffer playback.
2. Live short playback with guarded receiver connection.
3. Buffering and underflow/overflow diagnostics.

Open decisions:

- Audio backend: likely `sounddevice` first, but not chosen yet.
- Buffer target latency.
- How playback coexists with recording and detection consumers.

## Milestone 6 — Basic interactive client

Status: **Planned**

Goal:

Provide a simple local control surface for connecting, tuning, mode selection, and status.

Likely shape:

- Start with CLI or TUI for controls/status.
- Keep waterfall separate initially if easier.
- Keep protocol and transport separate from UI.

Capabilities needed:

- Connect/disconnect lifecycle.
- Tune frequency.
- Change mode/filter.
- Show sample rate, RSSI, sequence gaps, and receiver errors.

## Milestone 7 — Waterfall

Status: **Planned**

Goal:

Decode and display KiwiSDR waterfall frames.

Suggested order:

1. Inspect `kiwiclient/` W/F parser and fake server behavior.
2. Add synthetic W/F fixture.
3. Add W/F parser tests.
4. Capture a short local W/F fixture.
5. Build deterministic waterfall model.
6. Add a simple standalone waterfall view.

Note:

The waterfall view may initially be separate from the TUI/control surface.

## Milestone 8 — Beacon detection

Status: **Planned**

Goal:

Detect MF/LF radionavigation beacons from recorded or synthetic audio.

Suggested order:

1. Synthetic carrier present/absent tests.
2. Frequency offset tests.
3. Noise/fading tests.
4. Threshold/false-positive tests.
5. Recorded fixture tests.
6. Live capture validation only after detector harness coverage exists.

## Milestone 9 — Advanced weak-signal analysis

Status: **Planned**

Goal:

Longer-term integration and correlation for low-SNR signal detection.

Prerequisites:

- Stable recording pipeline.
- Detector harness.
- Long/large fixture storage policy.
- Reproducible offline analysis scripts.

## Maintenance rule

Update this roadmap whenever:

- a milestone moves status,
- a new capability is added,
- a planned capability is split or reordered,
- live-radio behavior changes the expected protocol or workflow,
- a major risk/open question is resolved.
