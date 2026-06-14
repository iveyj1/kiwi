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
