# Radio Lab Notes

## Receivers

| Name | Address | Notes |
|---|---|---|
| kiwi40 | `10.0.0.40:8073` | Primary; may have max users |
| kiwi41 | `10.0.0.41:8073` | Fallback |

## Live-test policy

Use local receivers only unless explicitly requested.

Prefer short tests.

Do not run unattended reconnect loops.

Do not issue admin or mutating commands.

## Live-test record template

```text
Date/time:
Receiver:
Frequency:
Mode:
Filter:
Stream type:
Purpose:
Commands sent:
Observed behavior:
Fixture captured:
Follow-up:
```

## Live-test log

### 2026-06-14 / 2026-06-13 local

```text
Date/time: 2026-06-14T02:17:52Z / 2026-06-13T22:17:52-04:00
Receiver: 10.0.0.40:8073
Frequency: 5000.000 kHz
Mode: AM
Filter: -5000..5000 Hz (10 kHz total)
Stream type: SND
Purpose: First guarded local SND fixture capture using uncompressed mono PCM path.
Commands sent:
  SET auth t=kiwi p=
  SET AR OK in=12000 out=44100
  SET squelch=0 max=0
  SET genattn=0
  SET gen=0 mix=-1
  SET ident_user=kiwi-client
  SET mod=am low_cut=-5000 high_cut=5000 freq=5000.000
  SET agc=1 hang=0 thresh=-100 slope=6 decay=1000 manGain=50
  SET compression=0
  SET keepalive
Observed behavior:
  Initial attempt connected but recorded binary MSG payloads as binary events and reached no SND frames.
  Capture tool was fixed to classify binary MSG payloads and to wait for audio_rate/sample_rate setup.
  Second short capture succeeded: 22 MSG events, 20 SND frames, seq 1..20, no gaps, 512 samples/frame.
  Receiver state: sample_rate=11998.94054, audio_rate=12000, version=1.842, bandwidth=30000000 Hz.
  RSSI range in captured frames was roughly -88 to -83 dB.
Fixture captured: tests/fixtures/kiwi/local-snd-5000-am-10khz.jsonl
Follow-up:
  Added regression test for fixture parse/sequence continuity.
  Consider recording exact message ordering in protocol docs and preserving binary-MSG handling.
```

### 2026-06-14 / 2026-06-13 local — direct WAV recording

```text
Date/time: 2026-06-14 after first fixture capture / 2026-06-13 local
Receiver: 10.0.0.40:8073
Frequency: 5000.000 kHz
Mode: AM
Filter: -5000..5000 Hz (10 kHz total)
Stream type: SND
Purpose: Verify guarded direct live-to-WAV recording path.
Commands sent:
  SET auth t=kiwi p=
  SET AR OK in=12000 out=44100
  SET squelch=0 max=0
  SET genattn=0
  SET gen=0 mix=-1
  SET ident_user=kiwi-client
  SET mod=am low_cut=-5000 high_cut=5000 freq=5000.000
  SET agc=1 hang=0 thresh=-100 slope=6 decay=1000 manGain=50
  SET compression=0
  SET keepalive
Observed behavior:
  Direct WAV recording succeeded: mono, 16-bit PCM, 11999 Hz, 10240 frames, 20 SND frames, zero sequence gaps.
  Duration was about 0.853 seconds of audio from 20 frames.
Fixture captured: none; output was recordings/live-snd-5000-am-10khz.wav (ignored by git)
Follow-up:
  Consider adding optional JSONL sidecar for direct live recording.
```

### 2026-06-14 / 2026-06-13 local — live playback

```text
Date/time: 2026-06-14 after direct WAV recording / 2026-06-13 local
Receiver: 10.0.0.40:8073
Frequency: 5000.000 kHz
Mode: AM
Filter: -5000..5000 Hz (10 kHz total)
Stream type: SND
Purpose: Verify guarded live SND playback path.
Commands sent:
  SET auth t=kiwi p=
  SET AR OK in=12000 out=44100
  SET squelch=0 max=0
  SET genattn=0
  SET gen=0 mix=-1
  SET ident_user=kiwi-client
  SET mod=am low_cut=-5000 high_cut=5000 freq=5000.000
  SET agc=1 hang=0 thresh=-100 slope=6 decay=1000 manGain=50
  SET compression=0
  SET keepalive
Observed behavior:
  Null-sink live playback succeeded first: 60 SND frames, 30720 audio frames, 61440 bytes, sample_rate=11999.
  Real sounddevice playback then succeeded from the software/API perspective with the same counts and dry_run=false.
Fixture captured: none
Follow-up:
  Add user-selectable audio device and buffering/underflow diagnostics.
```

### 2026-06-14 / 2026-06-13 local — background playback retune queue

```text
Date/time: 2026-06-14 after TUI background worker work / 2026-06-13 local
Receiver: 10.0.0.40:8073
Frequency: start 5000.000 kHz, queued tune to 7000.000 kHz
Mode: AM
Filter: -5000..5000 Hz (10 kHz total)
Stream type: SND
Purpose: Verify client/TUI background playback command queue with a short null-sink live run.
Commands/script:
  duration 5
  frames 120
  play-bg --allow-live --null-sink
  tune 7000
  wait 1
  operation-status
  stop
  wait 2
  operation-status
Observed behavior:
  The client queued `SET mod=am low_cut=-5000 high_cut=5000 freq=7000.000` while background playback was running.
  Null-sink playback continued and stopped cleanly after cooperative stop.
  Final result: 18 SND frames, 9216 audio frames, 18432 bytes, sample_rate=11999, no error.
Fixture captured: none
Follow-up:
  Add explicit control-command sent counters/status if we need stronger visibility than queued-command response.
```

### 2026-08-27 / 2026-08-27 local — zoomed AM waterfall mapping

```text
Date/time: 2026-08-27T04:43:33.928881Z / 2026-08-27T00:43:33.928884-04:00
Receiver: 10.0.0.40:8073
Frequency: requested center 855.000 kHz; mapped center 854.998827 kHz
Mode/filter: W/F stream only; not applicable
Stream type: W/F, zoom 7, speed 4, interp 13 (drop+CIC), wf_comp=0
Purpose: Confirm nonzero-zoom frequency mapping and bin orientation against known 760 and 950 kHz AM signals.
Commands sent:
  SET auth t=kiwi p=
  SET zoom=7 cf=855.000
  SET maxdb=0 mindb=-110
  SET wf_speed=4
  SET wf_comp=0
  SET interp=13
  SET keepalive
Observed behavior:
  Five 1024-bin frames captured without reconnect or admin commands.
  Receiver metadata: bandwidth=30000000 Hz, wf_fft_size=1024, zoom_max=14, wf_fps=23, zoom=7, start=412614.
  Mapped range: 737.811327..972.186327 kHz; span 234.375 kHz; 228.881836 Hz/bin.
  Averaged strong peaks occurred at about 760.127 and 949.870 kHz, matching the known AM signals and confirming bins increase left-to-right in frequency.
  Additional plausible AM-channel peaks appeared near 780.040, 799.953, 829.936, 840.007, 859.920, 889.903, and 909.816 kHz.
Fixture captured: tests/fixtures/kiwi/local-wf-am-855-zoom7.jsonl
Follow-up:
  Added fixture regression coverage for mapping and known carrier neighborhoods.
  Keep calibration/color-scale policy separate from frequency-coordinate validation.
```

### YYYY-MM-DD

```text
Date/time:
Receiver:
Frequency:
Mode:
Filter:
Stream type:
Purpose:
Commands sent:
Observed behavior:
Fixture captured:
Follow-up:
```
