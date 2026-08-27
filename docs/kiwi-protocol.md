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

Known guarded client MSG error handling:

- `MSG too_busy=<n>` -> `server busy: all <n> client slots are taken on <receiver>`.
- `MSG badp=1` -> `server busy or bad password: all no-password channels may be busy on <receiver>`.
- `MSG down` -> `server down: <receiver>`.
- `MSG redirect=<url>` -> `server redirected <receiver> to <url>`; local guarded tests do not follow redirects to non-local receivers.

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

Local captured W/F observations:

- `tests/fixtures/kiwi/local-wf-5000-zoom0.jsonl` was captured from `10.0.0.40:8073` on 2026-06-16 UTC at center 5000 kHz, zoom 0, `wf_comp=0`, speed 1.
- The receiver reported `MSG center_freq=15000000 bandwidth=30000000 adc_clk_nom=66666600`.
- The receiver reported `MSG wf_fft_size=1024 wf_fps=23 wf_fps_max=23 zoom_max=14 zoom_cap=14 rx_chans=4 wf_chans=4 wf_chans_real=4 wf_cal=-13 wf_setup` followed by `MSG zoom=0 start=0` and `MSG wf_fps=1`.
- The two captured W/F frames decoded with complete-message layout: 3-byte `W/F` tag, one raw flags byte, 12-byte little-endian W/F header, and 1024 raw bin bytes.
- Both captured frames had `raw_flags=32`, `x_bin_server=0`, `flags_x_zoom_server=0`, and `seq=0`. Because the two frames have different bin data and plausible waterfall intensity ranges, repeated `seq=0` is treated by the local tracker as an inactive/unknown W/F sequence counter rather than a real dropout. More captures are still needed before assigning exact sequence semantics.

### Zoomed W/F captures and frequency mapping

Three further local captures from `10.0.0.40:8073` on 2026-08-27 UTC, all `wf_comp=0`, `wf_speed=4`, 60 frames:

- `tests/fixtures/kiwi/local-wf-910-zoom8.jsonl` — center 910 kHz, `MSG zoom=8 start=476140`.
- `tests/fixtures/kiwi/local-wf-760-zoom9.jsonl` — center 760 kHz, `MSG zoom=9 start=408638`.
- `tests/fixtures/kiwi/local-wf-910-zoom11.jsonl` — center 910 kHz, `MSG zoom=11 start=504812`.

These captures resolve several previously open questions:

- **`x_bin_server` equals `MSG start`.** Both captures show the frame header field matching the `start` value reported in `MSG zoom=<z> start=<n>` exactly. At zoom 0 both are `0`, which is why the field looked unused in the first fixture.
- **`start` is expressed in zoom-max bin units**, not in bins at the current zoom. One count is `bandwidth / (wf_fft_size * 2**zoom_max)` = 1.788139 Hz for a 30 MHz, 1024-bin, `zoom_max=14` receiver.
- **`flags_x_zoom_server` carries zoom in its low bits.** Observed `8` at zoom 8 and `0x40009` at zoom 9. Only two samples exist, so the exact mask width is unconfirmed; `MSG zoom=` is the reliable source and the local helper `zoom_from_flags()` is marked provisional.
- **Span follows `bandwidth / 2**zoom` across all bins.** Fitting measured AM carrier positions gives a bin width within 1 part in 10^4 of the formula.

Resulting mapping, implemented as `WaterfallSpan` in `src/kiwi_client/waterfall.py`:

```text
unit_hz  = bandwidth / (wf_fft_size * 2**zoom_max)
start_hz = x_bin_server * unit_hz
bin_hz   = bandwidth / (wf_fft_size * 2**zoom)
span_hz  = bandwidth / 2**zoom

window center  = start_hz + (wf_fft_size / 2) * bin_hz
signal in bin i = start_hz + (i + BIN_CENTER_OFFSET) * bin_hz
```

The window center reproduces the tuned `cf` value to within a few Hz: 909.998 kHz and 759.999 kHz for captures tuned to 910 and 760.

> **The constant-offset model is known to be incomplete.** Live sweeps against WWVB and WWV show the offset varies with window position, so no single constant describes it. `0.83` remains in the code as the best working constant for bin selection, and every measured carrier still lands on its predicted bin, but the value below should be read as an approximation rather than a physical constant. See "The offset is not constant across window positions" at the end of this section.

**`BIN_CENTER_OFFSET = 0.83` is provisional and unexplained.**

What the offset is between: for a carrier of known frequency, the *naive* bin index `(f - start_hz) / bin_hz` and the *measured* index of its energy peak. Known AM carriers peak about 0.83 bins below the naive prediction. Stated as frequency instead, the signal in bin `i` sits at `start_hz + (i + 0.83) * bin_hz`.

The offset is **constant in bins, not in Hz.** The zoom-11 capture settles this: its bins are 8x narrower than the zoom-8 capture's, so a fixed frequency error would appear there as about 6.6 bins. The measured value is 1.0 bins. In Hz the discrepancy is 102 Hz at zoom 8, 51 Hz at zoom 9 and 13 Hz at zoom 11, tracking bin width. It is therefore a bin-indexing convention, not a tuning error or a bias in `start_hz`.

Requiring all 17 measured carriers to round onto their observed bins admits only:

```text
0.762 < offset <= 0.895
```

with the lower bound set by 750 kHz at zoom 9 and the upper by 920 kHz at zoom 8. The configured value is the center of that window, chosen to maximise margin against misbinning a carrier this data has not seen.

Two candidate explanations are ruled out:

- **A half-bin center convention (0.5).** Misplaces 7 of 17 carriers.
- **A whole-bin offset (1.0),** which would mean `x_bin_server` points one bin below the first displayed bin. Misplaces 3 of 17 carriers.

Parabolic interpolation of the same peaks in the dB domain gives a mean of 0.895 bins, but that falls exactly on the admissible window's upper edge, which suggests the interpolation is biased high rather than that 0.895 is the true value. Interpolation bias here is window-dependent and the receiver's FFT window is unknown.

Accuracy is not what is at stake in the choice: the whole admissible window spans 0.133 bins, which is about 7 Hz at zoom 8 and 1 Hz at zoom 11. Bin-selection robustness is. `tests/waterfall/test_frequency_mapping.py` asserts the configured value stays more than 0.05 bins clear of both edges.

#### Measuring the offset directly

`src/kiwi_client/waterfall_sweep.py` (`kiwi-wf-sweep`) narrows the offset without depending on broadcast-carrier tolerance. Against a reference of known exact frequency it steps the window past the tone, taking one constraint per window position; the intersection collapses once the peak crosses a bin boundary.

Precision is set by the step size rather than by the reference's frequency error, and is bounded by the number of window positions per bin, `2**(zoom_max - zoom)`:

| zoom | bin width | positions/bin | best precision |
| --- | --- | --- | --- |
| 8 | 114.4 Hz | 64 | 0.016 bins |
| 9 | 57.2 Hz | 32 | 0.031 bins |
| 10 | 28.6 Hz | 16 | 0.063 bins |
| 14 | 1.8 Hz | 1 | unusable |

Against a synthetic sweep with a planted offset the tool recovers a window 0.031 bins wide at zoom 9, about four times narrower than the 0.133 bins the AM carriers give.

Two effects trade off when choosing zoom. Narrower bins collect less atmospheric noise, worth roughly 3 dB of SNR per zoom step, which matters for a weak LF reference. But positions per bin halve at the same rate, so the sweep coarsens just as fast. Zoom 9 or 10 balances them.

Candidate references, in order of preference:

- **WWVB at 60 kHz**, cesium-referenced. Requires zoom 8 or higher, since lower zooms cannot center it and clamp against 0 Hz where bin 0 is dead. Its BPSK phase modulation at +/-45 degrees leaves roughly half the power in the discrete carrier line, and the AM ducking puts sidebands about 1 Hz out, which stays inside one bin down to about zoom 12.
- **WWV at 5, 10, 15 or 20 MHz**, equally accurate and clear of the LF noise floor. A sweep at 60 kHz and another at 10 MHz place `start` at values differing by a factor of several hundred, testing whether the offset depends on `start` at all.
- **The receiver's own signal generator** via `SET gen=`, locked to the same ADC clock as the FFT so any clock error cancels. Whether `gen` is global to the receiver or per-connection is unverified; if global it injects a tone into every other connected user, which the project's live-radio rules do not permit.

#### The offset is not constant across window positions

Two live sweeps were run against `10.0.0.40:8073` on 2026-08-27, both at zoom 9 with 40 window positions: WWVB at 60 kHz and WWV at 10 MHz. Compact records are committed at `docs/evidence/sweep-wwvb-60khz-zoom9.json` and `docs/evidence/sweep-wwv-10mhz-zoom9.json`, and `tests/waterfall/test_waterfall_sweep.py` asserts the findings below.

Both sweeps admit **no constant offset at all**. The measurements are:

| | WWVB 60 kHz | WWV 10 MHz |
| --- | --- | --- |
| mean offset | +0.907 bins | +0.903 bins |
| offset range across sweep | 1.062 bins | 1.062 bins |
| model positions per bin | 32.0 | 32.0 |
| **observed positions per bin** | **35.0** | **35.0** |

Two independent facts each rule out a constant:

- **The per-position offsets span 1.062 bins.** A constant offset can only produce a span below 1.0, because the offset equals the constant plus a quantisation residual in `[-0.5, +0.5)`.
- **Peak bin transitions fall 35 window positions apart**, where a constant offset requires exactly `2**(zoom_max - zoom)` = 32. The effective offset drifts about 0.094 bins between consecutive transitions.

Both references give **identical** structure, matching to about 0.003 bins at every position, despite 60 kHz versus 10 MHz and `start` values differing by a factor of roughly 300 (17148 versus 5576006). So the effect depends on window position, not on frequency or on absolute `start`.

This is genuinely puzzling, because two other measurements independently confirm the pieces the sweep contradicts:

- Bin width is confirmed as `bandwidth / (1024 * 2**zoom)` by AM carrier spacing: 11 carriers spanning 100 kHz across 874 bins at zoom 8, and 5 spanning 40 kHz across 699 bins at zoom 9.
- `unit_hz` is confirmed as `bandwidth / (1024 * 2**zoom_max)` by window centre recovery, which reproduces the tuned `cf` to within a few Hz at zooms 8, 9 and 11.

Given both, `bin_width / unit_hz` must be exactly 32, yet stepping `start` by 35 counts is what moves the peak by one bin. The likely explanation is that the receiver's actual passband does not move by exactly one `unit_hz` per reported `x_bin_server` count during retuning, which would make `x_bin_server` an accurate label for a window but not a linear measure of its position. Confirming that needs the KiwiSDR BeagleBone and DSP sources rather than more black-box captures.

Deferred deliberately, and probably permanently. The waterfall is a visualization path, not a measurement path: it delivers 8-bit dBm quantised to 1 dB, with receiver-side `interp` smoothing already applied, and no phase. Accurate frequency work belongs to the SND audio stream instead, which preserves full 16-bit PCM, keeps phase, offers IQ mode, and reports its own `sample_rate` to six decimals so the timebase can be corrected. The waterfall exposes no equivalent and derives everything from the nominal `bandwidth`.

That makes the offset a display concern only, affecting axis labels and cursor readout rather than any measurement. The working constant already puts every measured carrier on the correct bin, which is all a display needs. Revisit only if the waterfall itself ever needs sub-bin labelling.

Evidence for the mapping, all fixture-backed and network-free in `tests/waterfall/test_frequency_mapping.py`:

- All 11 AM channels from 860 to 960 kHz in the zoom-8 capture peak on the predicted bin.
- All 5 AM channels from 740 to 780 kHz in the zoom-9 capture peak on the predicted bin.
- The single AM channel in the zoom-11 window, 910 kHz, peaks on the predicted bin. A test asserts that window really does contain exactly one 10 kHz channel, so this single-carrier check cannot silently pass on a mis-tuned capture.
- Each of those peaks is more than 6 dB above the median bin level, so the tests are measuring carriers rather than noise.
- A dedicated test asserts the Hz-constant hypothesis predicts the wrong bin at zoom 11 while the bin-constant one predicts the right bin.

Other observations from these captures:

- `seq` remained `0` for all 60 frames at `wf_fps=23`, so repeated zero is not an artifact of the earlier 1 fps capture. W/F sequence still appears inactive on this receiver.
- The receiver reported `rx_chans=8 wf_chans=3 wf_chans_real=3 wf_share=1 zoom_cap=11`, differing from the 2026-06-16 capture's `rx_chans=4 wf_chans=4 wf_chans_real=4 zoom_cap=14`. Either the receiver was reconfigured or these are different hosts behind the same address. **`zoom_cap` is the effective ceiling, not `zoom_max`.**
- `SET wf_speed=4` produced `MSG wf_fps=23`, matching the reported `wf_fps_max`. The earlier `SET wf_speed=1` produced `MSG wf_fps=1`.
- Carriers falling near a bin boundary split across two adjacent bins with nearly equal amplitude, e.g. 950 kHz at fractional bin position 0.71 gives bin 860 at -39 dBm and bin 861 at -38 dBm. Carriers near a bin center do not, e.g. 910 kHz at fractional position 0.18 gives a single peak with neighbours 10 dB down. This is ordinary FFT scalloping and is a property of the receiver's FFT, not of any display reduction.

Still to verify with project fixtures:

- The cause of the provisional 0.83 bin center offset. Constancy in bins is settled and both 0.5 and 1.0 are excluded; identifying the receiver's FFT window is the likely next step.
- `flags_x_zoom_server` bit layout beyond the low zoom bits.
- Calibration and display scaling policy, including how `wf_cal=-13` should be applied.
- Timing/update behavior for `wf_speed` values 2 and 3.
- Compressed W/F payload behavior.
- Whether `wf_share=1` changes frame timing or content.

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
Fields: mode, low/high passband cuts in Hz, radio frequency in kHz. The default encoder emits 3 decimal places, but the client can be configured to emit more (e.g. 4 decimals for sub-Hz tuning). For project CW tuning, the UI/user frequency is passband center and the command `freq` is offset by configured `cw_offset_hz`.
Example: SET mod=am low_cut=-4900 high_cut=4900 freq=4625.000
CW example with user/passband frequency 335.000 kHz and `cw_offset_hz=-800`: SET mod=cw low_cut=650 high_cut=1050 freq=334.200
Sub-Hz example with 4 command decimals: SET mod=cw low_cut=650 high_cut=1050 freq=4999.2005
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
