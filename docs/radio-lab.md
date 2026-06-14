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
