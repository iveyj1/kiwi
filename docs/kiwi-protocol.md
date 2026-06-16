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
- `tests/fixtures/kiwi/local-snd-5000-am-10khz.jsonl` contains a short local live capture from `10.0.0.40:8073`. The receiver delivered `MSG` frames as binary WebSocket payloads beginning with ASCII `MSG`; the capture tool records these as JSONL `msg` events after tag inspection.

Live local capture observations:

- On `10.0.0.40:8073`, `MSG sample_rate` arrived before `MSG audio_init=1 audio_rate=12000` during the tested session.
- After `audio_rate=12000`, sending `SET AR OK in=12000 out=44100` was needed before the remaining SND setup sequence.
- The first successful uncompressed AM capture used: `SET squelch=0 max=0`, `SET genattn=0`, `SET gen=0 mix=-1`, identity, modulation, AGC, `SET compression=0`, and keepalive.

Still to record after more fixture-backed live captures exist:

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

Additional fixture coverage:

- `tests/fixtures/kiwi/snd-sequence-gap.jsonl` contains synthetic uncompressed mono frames with sequence numbers `1, 3, 4`, covering a missing frame at expected sequence `2`.
- `tests/fixtures/kiwi/local-snd-5000-am-10khz.jsonl` contains 20 live uncompressed mono SND frames at 5000 kHz AM, sequences `1..20`, 512 samples per frame, no gaps.
- `src/kiwi_client/audio.py` treats SND sequence numbers as uint32 values and accepts wraparound from `0xffffffff` to `0`.
- ADC overflow is exposed via flag `0x02`; fixture-backed parser code preserves flags for audio-layer handling.

Remaining SND questions:

- Exact ADPCM codec state/reset expectations for compressed mono fixtures.
- Real receiver dropout behavior under network loss or load.
- Whether local receivers report `sample_rate` exactly 12000 or drifted values in normal sessions.
- Live capture metadata and command sequence to preserve once harness tests exist.

## Waterfall stream

Synthetic fixture-backed behavior:

- Stream type is `W/F`.
- WebSocket binary messages begin with 3-byte ASCII tag `W/F`.
- The first parser target treats the byte after the tag as `raw_flags`, then decodes a 12-byte W/F body header as three little-endian uint32 values: `x_bin_server`, `flags_x_zoom_server`, and `seq`, followed by bin payload bytes.
- Uncompressed W/F frames expose remaining payload bytes as uint8 bins.
- Raw-byte intensity mapping uses `dBm = sample - 255` before calibration.

Fixture/test coverage:

- `tests/fixtures/kiwi/wf-basic.jsonl` contains one synthetic uncompressed W/F frame.
- `tests/protocol/test_waterfall.py` covers tag, header, bin, dBm mapping, and malformed frame handling.

Reference-backed planning facts, not yet locally fixture-verified:

- Reference default bin count is `WF_BINS = 1024`.
- Uncompressed W/F setup uses `SET wf_comp=0`.
- Reference setup commands include `SET zoom=<zoom> cf=<center_khz>`, `SET maxdb=<maxdb> mindb=<mindb>`, `SET wf_speed=<1..4>`, `SET wf_comp=<0|1>`, and `SET interp=<value>`.

Evidence:

- `kiwiclient/kiwi/client.py`
- `kiwiclient/kiwirecorder.py`
- `kiwiclient/microkiwi_waterfall.py`
- Planning spec: `docs/waterfall-spec.md`

Still to verify with project fixtures:

- Exact complete-message byte layout from local receivers.
- `x_bin_server` and `flags_x_zoom_server` semantics.
- Frequency span/bin mapping for local receiver versions.
- Calibration and display scaling policy.
- Timing/update behavior for each `wf_speed` value.
- Compressed W/F payload behavior.
- Fixture coverage under `tests/fixtures/kiwi/wf-basic.jsonl` and later a local captured W/F fixture.

## Commands

Initial fixture-tested non-admin SND setup command encoders:

```text
Command: SET auth t=kiwi p=
Direction: client -> server
Purpose: Authenticate as a normal Kiwi client with no password.
Fields: client type `t`, password `p`.
Example: SET auth t=kiwi p=
Evidence: `kiwiclient/kiwi/client.py` `_set_auth()`.
Fixture/test: `tests/fixtures/kiwi/snd-setup-commands.jsonl`, `tests/protocol/test_commands.py`.
Failure behavior: TBD after live/local fixture capture.

Command: SET ident_user=<name>
Direction: client -> server
Purpose: Set displayed/listed user identity.
Fields: identity string.
Example: SET ident_user=kiwi-client
Evidence: `kiwiclient/kiwi/client.py` `set_name()`.
Fixture/test: `tests/fixtures/kiwi/snd-setup-commands.jsonl`, `tests/protocol/test_commands.py`.
Failure behavior: TBD.

Command: SET mod=<mode> low_cut=<Hz> high_cut=<Hz> freq=<kHz>
Direction: client -> server
Purpose: Set demodulation mode, passband, and tuned frequency.
Fields: mode, low/high passband cuts in Hz, frequency in kHz with 3 decimal places.
Example: SET mod=am low_cut=-4900 high_cut=4900 freq=4625.000
Evidence: `kiwiclient/kiwi/client.py` `set_mod()`.
Fixture/test: `tests/fixtures/kiwi/snd-setup-commands.jsonl`, `tests/protocol/test_commands.py`.
Failure behavior: TBD.

Command: SET agc=<0|1> hang=<0|1> thresh=<dB-ish> slope=<n> decay=<ms-ish> manGain=<n>
Direction: client -> server
Purpose: Configure AGC.
Fields: AGC enable, hang enable, threshold, slope, decay, manual gain.
Example: SET agc=1 hang=0 thresh=-100 slope=6 decay=1000 manGain=50
Evidence: `kiwiclient/kiwi/client.py` `set_agc()`.
Fixture/test: `tests/fixtures/kiwi/snd-setup-commands.jsonl`, `tests/protocol/test_commands.py`.
Failure behavior: TBD.

Command: SET compression=<0|1>
Direction: client -> server
Purpose: Request SND audio compression on/off; first fixtures use `0` for uncompressed PCM.
Fields: compression enable.
Example: SET compression=0
Evidence: `kiwiclient/kiwi/client.py` `_set_snd_comp()`.
Fixture/test: `tests/fixtures/kiwi/snd-setup-commands.jsonl`, `tests/protocol/test_commands.py`.
Failure behavior: TBD.

Command: SET keepalive
Direction: client -> server
Purpose: Keep SND session alive.
Fields: none.
Example: SET keepalive
Evidence: `kiwiclient/kiwi/client.py` `_set_keepalive()` and SND receive loop.
Fixture/test: `tests/fixtures/kiwi/snd-setup-commands.jsonl`, `tests/protocol/test_commands.py`.
Failure behavior: timeout behavior TBD.
```

Record each future command as:

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
