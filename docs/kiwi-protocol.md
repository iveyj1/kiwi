# KiwiSDR Protocol Notes

This file records locally verified KiwiSDR protocol behavior.

## Evidence policy

Each protocol fact should cite its evidence source:

- `kiwiclient/` reference code
- Upstream KiwiSDR source if available locally
- Captured fixture
- Browser observation
- Live local receiver test

Prefer fixture-backed facts.

## Local receivers

- `10.0.0.40:8073`
- `10.0.0.41:8073`

## Connection/session notes

Initial reference facts from `kiwiclient/kiwi/client.py` and `kiwiclient/test/kiwi_server.py`:

- WebSocket messages begin with a 3-byte ASCII tag, e.g. `MSG`, `SND`, `W/F`.
- `MSG` messages contain space-separated parameters after the tag. In normal text form this appears as `MSG name=value name2=value2`; the reference client skips the first byte of the body, which is typically the space after `MSG`.
- Parameters may be `name=value` or flag-like `name` with no value.
- Some values are percent-escaped; the reference client unquotes selected fields such as `extint_list_json` and configuration payloads.
- Important early SND session parameters:
  - `audio_rate`: integer audio output/acknowledgement rate used by the Kiwi client handshake.
  - `sample_rate`: floating-point receiver sample rate used for audio timing.
  - `version_maj`, `version_min`: Kiwi server version parts.
  - `bandwidth`: receiver bandwidth in Hz.

Current fixture coverage:

- `tests/fixtures/kiwi/snd-session-basic.jsonl` contains synthetic `MSG` events for `audio_rate`, `sample_rate`, version, and bandwidth followed by one synthetic uncompressed mono SND frame.

Still to record after a fixture-backed live capture exists:

- WebSocket endpoint paths
- Initial handshake/control command order
- Stream selection
- Authentication or identity fields, if any
- Error/max-user behavior
- Reconnect behavior

## SND/audio stream

Initial reference facts from `kiwiclient/kiwi/client.py` and `kiwiclient/test/kiwi_server.py`:

- WebSocket binary messages begin with a 3-byte ASCII tag. SND audio messages use tag `SND`.
- The SND body begins at byte 3 of the WebSocket payload.
- SND body header:
  - `flags`: 1 byte.
  - `seq`: 4-byte unsigned integer, little-endian.
  - `smeter`: 2-byte unsigned integer, big-endian in the client decoder.
  - `data`: remaining bytes.
- RSSI conversion in reference client: `rssi = 0.1 * smeter - 127` dB.
- Known flag bits from reference client:
  - `0x02`: ADC overflow.
  - `0x08`: stereo.
  - `0x10`: compressed ADPCM audio.
  - `0x80`: little-endian sample data while camping.
- Non-camping, non-stereo, uncompressed mono samples are signed 16-bit big-endian PCM.
- Non-camping stereo/IQ mode prepends a 10-byte little-endian GPS timestamp structure to sample data, then interleaves signed 16-bit big-endian I/Q samples.
- Normal non-camping mono defaults to compression enabled unless the client sends `SET compression=0`; fixture-first tests should start with uncompressed mono and add compressed ADPCM later.
- The reference fake server emits synthetic SND frames but uses zero S-meter, so it does not prove S-meter endianness.

First fixture coverage:

- `tests/fixtures/kiwi/snd-basic.jsonl` contains one synthetic uncompressed mono SND WebSocket payload with `flags=0`, `seq=1`, `smeter=850` (`rssi=-42.0`), and samples `[-32768, -1, 0, 1, 32767]`.

Remaining SND questions:

- Exact ADPCM codec state/reset expectations for compressed mono fixtures.
- Dropout behavior and sequence wrap handling.
- Whether local receivers report `sample_rate` exactly 12000 or drifted values in normal sessions.
- Live capture metadata and command sequence to preserve once harness tests exist.

## Waterfall stream

TBD.

Record:

- Frame prefix/type
- Frame dimensions
- Bin mapping
- Frequency span
- Intensity scaling
- Timing/update rate
- Fixture coverage

## Commands

TBD.

Record each command as:

```text
Command:
Direction:
Purpose:
Fields:
Units:
Example:
Evidence:
Fixture/test:
Failure behavior:
```

## Known open questions

- Exact audio frame format used by local receivers.
- Exact control command sequence for frequency and mode changes.
- Whether waterfall and audio streams need independent sessions.
- Best fixture representation for binary stream data.
