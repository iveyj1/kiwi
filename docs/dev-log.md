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

### Follow-up

Next useful slice: implement an offline capture-writer shape or fake transport replay for the planned short SND capture. Live receiver access remains deferred until the capture tool can write the documented JSONL metadata/events.

## YYYY-MM-DD

### Finding

### Decision

### Test result

### Follow-up
