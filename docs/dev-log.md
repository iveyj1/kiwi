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

## YYYY-MM-DD

### Finding

### Decision

### Test result

### Follow-up
