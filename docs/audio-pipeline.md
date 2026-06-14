# Audio Pipeline

## Purpose

Convert KiwiSDR audio stream data into stable playback, recording, and analysis input.

## First fixture-based SND audio test plan

### Scope for the first harness slice

Start with protocol/audio conversion only, not playback:

1. Read JSONL fixture events from `tests/fixtures/kiwi/snd-basic.jsonl`.
2. For `rx`/`binary`/`stream=snd` events, base64-decode the full WebSocket payload.
3. Parse the first 3 bytes as the tag and require `SND`.
4. Parse the SND body header as `flags:u8`, `seq:u32le`, `smeter:u16be`.
5. Convert RSSI as `0.1 * smeter - 127`.
6. For first fixture only, require uncompressed mono (`flags & 0x10 == 0`, `flags & 0x08 == 0`) and decode remaining bytes as signed 16-bit big-endian PCM.
7. Assert exact values from the synthetic fixture:
   - `seq == 1`
   - `flags == 0`
   - `smeter == 850`
   - `rssi == -42.0`
   - samples are `[-32768, -1, 0, 1, 32767]`

### First test names to add

- `test_snd_fixture_loads_jsonl_events`
- `test_snd_uncompressed_mono_header_fields`
- `test_snd_uncompressed_mono_pcm_big_endian`
- `test_snd_rejects_truncated_header`
- `test_snd_rejects_odd_pcm_byte_count`

### Follow-on harness cases before live radio

- Multiple sequential SND frames with sequence continuity checks.
- ADC overflow flag exposure (`flags & 0x02`).
- `SET compression=0` command fixture around an uncompressed capture session.
- Compressed mono ADPCM decode fixture after the reference decoder is isolated or reimplemented.
- Stereo/IQ fixture with 10-byte GPS header and interleaved samples.

## Session state context

The first stateful harness path uses `tests/fixtures/kiwi/snd-session-basic.jsonl`:

1. Apply received `MSG` parameters to a minimal receiver state.
2. Preserve `sample_rate` as a floating-point value from `MSG sample_rate`.
3. Preserve `audio_rate`, Kiwi version fields, and receiver bandwidth for later diagnostics.
4. Decode subsequent SND audio frames separately from state updates.

This keeps protocol parsing, receiver state, and audio sample conversion separate while allowing later audio buffers to carry sample-rate context.

## Sequence/dropout handling

`src/kiwi_client/audio.py` adds an audio-layer `SndSequenceTracker`:

- First observed frame establishes the next expected sequence.
- Normal continuity expects `seq == previous_seq + 1` modulo `2^32`.
- Gaps report `missing_count` so later buffering/recording can log dropouts.
- Very large reverse deltas are treated as out-of-order frames.
- Wraparound from `0xffffffff` to `0` is accepted.

Fixture coverage:

- `tests/fixtures/kiwi/snd-sequence-gap.jsonl` contains frames `1, 3, 4`; the tracker reports one missing frame at expected sequence `2`.
- `tests/audio/test_snd_sequence.py` covers gap detection, wraparound, out-of-order detection, and ADC overflow flag exposure.

## Questions to resolve

- Whether audio frames should directly carry a `sample_rate` snapshot or whether consumers should pair frames with receiver state.
- Final sample scaling for playback/detector handoff: keep `int16` initially, add `float32` only at consumer boundaries.
- Mono/stereo handling beyond the first mono fixture.
- Audio codec/compression fixture strategy.
- Buffer target latency.
- Recording format.
- Detector handoff format.

## Design constraints

- Keep protocol decoding separate from playback.
- Make audio conversion testable from fixtures.
- Log underflow/overflow/dropout conditions.
- Allow later recording and detector consumers without rewriting playback.
