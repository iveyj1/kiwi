# Dev Log

Use this as lightweight project memory. Record facts that future agent sessions should not rediscover.

## 2026-06-13

### Finding

`kiwiclient/kiwi/client.py` decodes SND WebSocket payloads as a 3-byte `SND` tag followed by `flags:u8`, `seq:u32le`, `smeter:u16be`, then audio data. Non-camping, uncompressed mono audio is signed 16-bit big-endian PCM. RSSI is `0.1 * smeter - 127`.

### Decision

First harness tests use `tests/fixtures/kiwi/snd-basic.jsonl`, a synthetic uncompressed mono SND frame, before any live receiver connection. Compressed ADPCM and stereo/IQ fixtures are explicitly follow-on work.

Waterfall rendering may start as a separate lightweight view/process from any TUI if that keeps the early TUI focused on controls/status.

### Test result

`python3 -m pytest tests/harness tests/protocol` passed: 5 tests.

Added minimal `MSG` parsing and receiver state context. `tests/fixtures/kiwi/snd-session-basic.jsonl` now covers synthetic `audio_rate`, `sample_rate`, version, and bandwidth `MSG` events followed by one uncompressed mono SND frame. `ReceiverState` tracks those values separately from audio frame parsing.

`python3 -m pytest` passed: 10 tests.

Added fixture-tested command encoders for the first non-admin SND setup path: auth, identity, mode/frequency/passband, AGC, compression off, and keepalive. `tests/fixtures/kiwi/snd-setup-commands.jsonl` records the expected command sequence.

Documented the first short SND live-to-fixture capture plan in `docs/harness.md`, but did not run it.

`python3 -m pytest tests/harness tests/protocol` passed: 15 tests.

Committed as `dc44b44` (`Add fixture-tested SND command encoders`).

Added offline JSONL capture writer shape in `src/kiwi_client/capture.py`. It records SND capture metadata, tx commands, rx MSG events, and rx binary WebSocket payloads. `tests/harness/test_capture_writer.py` round-trips a synthetic capture through the fixture loader, MSG parser, receiver state, and SND parser.

`python3 -m pytest tests/harness tests/protocol` passed: 16 tests.

### Follow-up

Committed as `68770f5` (`Add offline SND capture fixture writer`).

Added strict offline `ReplayTransport` in `src/kiwi_client/transport.py`. It consumes fixture events in order, validates transmitted commands, and returns received MSG/binary events. `tests/harness/test_replay_transport.py` covers successful setup/session replay and command mismatch failure.

`python3 -m pytest tests/harness tests/protocol` passed: 18 tests.

Next useful slice: add the first guarded live capture command-line tool while leaving actual execution for a separate explicit live-radio-test step, or add more parser coverage for sequence/dropout handling before live capture.

Added audio-layer SND sequence/dropout handling. `SndSequenceTracker` detects missing frames, out-of-order frames, and uint32 wraparound. `tests/fixtures/kiwi/snd-sequence-gap.jsonl` covers frames `1, 3, 4` with one missing frame at expected sequence `2`. ADC overflow flag exposure is covered in audio tests.

`python3 -m pytest` passed: 22 tests.

Committed as `1491c70` (`Add SND sequence gap tracking`).

Added guarded SND live capture module/CLI in `src/kiwi_client/live_capture.py`. It supports dry-run without network, validates the local receiver allowlist, caps duration/frame count, refuses overwrites by default, requires `--allow-live` for actual network use, and writes JSONL via the existing capture writer. Actual live execution was not run.

Dry-run command verified with no network: `PYTHONPATH=src python3 -m kiwi_client.live_capture --dry-run --host 10.0.0.40 --output /tmp/kiwi-dry-run.jsonl --timestamp 123456`.

`python3 -m pytest` passed: 28 tests.

Live local SND capture requested and run against `10.0.0.40:8073` at 5000 kHz AM, filter `-5000..5000` Hz. First attempt connected but showed that live Kiwi MSG frames can arrive as binary WebSocket payloads with `MSG` tag; tool classified them as binary and got no SND frames. Updated the capture flow to classify binary MSG payloads, wait for `audio_rate`, send `SET AR OK in=12000 out=44100`, then send squelch/gen/identity/mod/AGC/compression/keepalive setup.

Second guarded capture succeeded and wrote `tests/fixtures/kiwi/local-snd-5000-am-10khz.jsonl`: 22 MSG events, 20 SND frames, seq `1..20`, 512 samples/frame, no parse errors, no sequence gaps. Receiver state was `sample_rate=11998.94054`, `audio_rate=12000`, version `1.842`, bandwidth `30000000` Hz. Added regression coverage in `tests/harness/test_local_snd_capture.py`.

Added offline fixture-to-WAV recording in `src/kiwi_client/recorder.py`. The first recording path writes uncompressed mono SND fixture samples as standard 16-bit PCM WAV, rounding the fixture `sample_rate` to integer Hz for the WAV header. `tests/audio/test_wav_recorder.py` validates the local 5000 kHz fixture produces 20 SND frames, 10240 WAV frames, 11999 Hz, mono, 16-bit, with zero sequence gaps.

Committed as `d73615e` (`Add fixture WAV recording`).

Added a user-facing fixture-to-WAV CLI via `python3 -m kiwi_client.recorder` and project script `kiwi-fixture-to-wav`. The CLI supports `--json` summary output and was used to refresh `recordings/local-snd-5000-am-10khz.wav` from the live radio fixture. Generated recordings remain ignored by git.

Committed as `c31d4ce` (`Add fixture to WAV recorder CLI`).

Added `docs/roadmap.md` as the high-level milestone tracker. It records completed SND harness, guarded local capture, and offline WAV recording milestones, and identifies direct live-to-WAV recording as the recommended next milestone. `docs/project-brief.md` now links to the roadmap. Roadmap maintenance rule: update it whenever milestone status, ordering, protocol behavior, or major risks change.

Committed as `b1ff2af` (`Add project roadmap`).

Advanced Milestone 4 direct live-to-WAV recording: added `src/kiwi_client/live_record.py` with replay-tested direct SND-to-WAV session logic and a guarded live CLI requiring `--allow-live`. Replay coverage uses the local 5000 kHz fixture and validates WAV output without network access.

Started Milestone 5 playback: added `src/kiwi_client/playback.py` with an `AudioSink` interface, `NullAudioSink`, WAV chunk reader, and dry-run CLI. Real audio-device output remains pending.

Dry-runs verified:

- `PYTHONPATH=src python3 -m kiwi_client.live_record --dry-run ...`
- `PYTHONPATH=src python3 -m kiwi_client.playback recordings/local-snd-5000-am-10khz.wav --dry-run --json`

Ran one guarded direct live-to-WAV recording against `10.0.0.40:8073`, 5000 kHz AM, filter `-5000..5000` Hz. Output `recordings/live-snd-5000-am-10khz.wav` was mono 16-bit PCM, 11999 Hz, 10240 frames, 20 SND frames, zero sequence gaps. Generated WAV is ignored by git.

Committed as `22facb5` (`Advance direct recording and playback milestones`).

Implemented guarded live SND playback in `src/kiwi_client/live_play.py`. Added `SoundDeviceSink` to `playback.py` using optional `sounddevice`, plus replay/null-sink tests. Installed `sounddevice` locally and confirmed default output device exists. Ran live playback first with `--null-sink` and then real audio output against `10.0.0.40:8073`, 5000 kHz AM, filter `-5000..5000` Hz. Both runs processed 60 SND frames, 30720 audio frames, 61440 bytes, sample rate 11999 Hz; real run reported `dry_run=false`.

Committed as `9c47013` (`Add guarded live SND playback`).

Started Milestone 6 with `src/kiwi_client/client_app.py`, a scriptable control shell that keeps app state separate from protocol/transport/audio layers. It supports status, connect/disconnect state, receiver, tune, mode/filter, and dry-run plans for play/record/capture. `kiwi-client` project script added. No live receiver connection was made for this slice.

## YYYY-MM-DD

### Finding

### Decision

### Test result

### Follow-up
