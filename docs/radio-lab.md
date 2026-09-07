# Radio Lab Notes

## 2026-08-28 — User-reported proxy combined W/F + SND validation

- Receiver: `misdr.proxy.kiwisdr.com:8073` (explicitly selected by user; not contacted by the agent).
- Report time: approximately 2026-08-28 03:07 UTC / 2026-08-27 23:07 local.
- Working configuration defaults: 5000 kHz, AM, passband -5000..5000 Hz, W/F zoom 7, speed 4, interp 13, `--audio` enabled.
- Observation: combined waterfall and audible audio work after opening/authenticating SND before paired W/F with one shared session timestamp.
- Previous failure: W/F-first ordering caused proxy close code 1005 as soon as audio was added, even with a shared timestamp.
- Fixture: none; this is user-reported external proxy validation. Deterministic fake-runner ordering coverage remains in the harness.

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

### 2026-09-07 — user Verizon hotspot and switch-freeze observations

```text
Network: Verizon hotspot
Receivers: paired-working public registers 8, 9, a, and b
Observation: user confirmed all four paired SND/W/F receivers work. During repeated receiver switching, both SND and W/F later stopped. Switching to another receiver did not recover either stream; restarting kiwi-console recovered operation.
Comparison: user reports other machines show results similar to prior public-receiver tests over Starlink, while LAN receivers have been consistently successful.
Follow-up: reproduce with fake delayed/stalled transports, add first-data/stall status deadlines, and verify old worker/event-loop teardown before replacement startup. Do not assume another receiver switch is sufficient recovery.
```

### 2026-09-07 — public paired SND/W/F sample over Starlink

```text
Date/time: approximately 2026-09-07T16:56Z UTC
Network: Starlink (reported by user); user reports 100% paired success on LAN/local receivers and prior 0% on selected Starlink/public attempts
Receivers/settings: ten public-directory receivers plus configured r7; 1000 kHz AM, W/F zoom 0/speed 1/interp 13, null local sink
Method: normal shared-timestamp paired SND/W/F, sequential, stop as soon as both streams produced data or after eight seconds, no retries/admin commands
Both SND and W/F succeeded: kiwisdr.areg.org.au:8074 (2.2s), oh6hps.ddns.net:8073 (2.2s), hl5ntr.ddns.net:8074 (2.2s), sdr.rogerh.co.nz:8073 (5.3s)
Explicit capacity/password errors: 178.17.3.34:8073 (all 4 client slots occupied), oh3aa.dy.fi:18073 (all no-password channels may be busy)
Both sockets opened but no protocol data in eight seconds: sa4bna.hopto.org:8073, sk6ag2.ddns.net:8072, tredxk.no-ip.org:8075, g3sdr.com:8078
Configured r7 partial success: kiwisdr.moxley.us:8073 produced 163 SND frames but zero W/F frames in eight seconds
Observation: paired operation does work over the current Starlink path, disproving a universal Starlink transport failure. Receiver load/policy and silent-open behavior vary. Current `snd_status=running` / `wf_status=running` means sockets/tasks started, not that protocol data arrived; per-stream first-data status and timeout diagnostics are needed.
Fixture captured: none; successful streams matched existing fixtures and no protocol behavior changed
Follow-up: add first-message/first-frame status deadlines, then repeat the same receiver set through the planned hotspot for a controlled network-path comparison
```

### 2026-09-07 — ten-receiver public-directory W/F sample

```text
Date/time: 2026-09-07T16:49Z–16:52Z UTC
Source: http://kiwisdr.com/public/ after the documented click-through request; receivers explicitly requested by user
Settings: W/F only, 1000 kHz, zoom 0, speed 1, interp 13; sequential tests stopping after one frame or three seconds; no retries
Successful first frame: kiwisdr.areg.org.au:8074, 178.17.3.34:8073, oh3aa.dy.fi:18073, hl5ntr.ddns.net:8074
Silent for three seconds: sa4bna.hopto.org:8073, sk6ag2.ddns.net:8072, tredxk.no-ip.org:8075, sdr.rogerh.co.nz:8073, g3sdr.com:8078
Explicit busy/password response: oh6hps.ddns.net:8073 (all no-password channels may be busy)
Inconclusive directory redirect entries replaced in the sample: bern.proxy.kiwisdr.com, n0bqv.proxy.kiwisdr.com, pb8w.proxy.kiwisdr.com omitted ports and redirected WebSocket requests to an http:// URI rejected by the websockets library
Observation: 4/10 produced valid standalone W/F immediately, proving non-local W/F transport and parsing. All four successes advertised ext_api >= 2 (three reported 4; one reported 2). K8BMZ advertises ext_api=1 and can provide either standalone W/F or SND but not both independent streams. Public receiver availability/policy varies substantially and combined console failure remains distinct from standalone parser capability.
Fixture captured: none; all successful payloads matched existing protocol coverage
Follow-up: test browser-style combined association only on a cooperative receiver and avoid implementing a two-allocation fallback
```

### 2026-09-07 — unpaired parallel external SND/W/F

```text
Date/time: approximately 2026-09-07T12:41Z UTC
Receivers: kiwi.k8bmz.net:8073 (r5), then kx4az-t2.proxy.kiwisdr.com:8073 (r4); both explicitly requested external tests
Frequency/mode/settings: nominal 298.000 kHz, CW receiver 297.200 kHz, cuts +600..+1000 Hz, W/F zoom 7/speed 4/interp 13
Stream type: independent parallel SND and W/F, distinct timestamps separated by 37, five-second bounds, null sink
Purpose: determine whether unpaired sessions restore W/F and whether they consume two allocations
Commands sent: normal non-admin auth/setup only; no reconnect loops
Observed behavior: on K8BMZ (`ext_api=1`), W/F received 63 valid frames while SND received no initial message or audio. This demonstrates that the independent sessions compete for separate external-API allocations rather than forming one receiver session; only one can succeed with the advertised single allocation. On KX4AZ-T2 (`ext_api=4`), neither stream returned an initial message in the bounded test, consistent with unavailable/full or policy-blocked API allocations at that time. Unpaired parallel operation therefore does not provide an acceptable combined fallback and can tie up two receiver allocations when available.
Fixture captured: none; K8BMZ W/F matched existing parser behavior and no new protocol payload was discovered
Follow-up: do not adopt unpaired parallel mode as the default; investigate browser session association/cookies/connection identity or accept receiver external-API policy limitations
```

### 2026-09-07 — K8BMZ standalone versus paired external W/F

```text
Date/time: approximately 2026-09-07T12:25Z UTC
Receiver: kiwi.k8bmz.net:8073 (register 5, external receiver explicitly supplied by user)
Frequency/mode/settings: 298 kHz, CW, zoom 7, speed 4, interp 13
Stream type: bounded W/F-only and paired SND/W/F comparisons, null local sink
Purpose: determine whether non-local W/F parsing or paired allocation fails
Commands sent: normal non-admin auth/setup only; no reconnect loops
Observed behavior: presets.toml has no password and URL normalization is correct. HTTP /status reported active, users=2/8, mode=rx8.wf3, ext_api=1. Standalone project W/F received 37 valid frames in five seconds, proving external transport and parsing work. Paired runs received normal SND frames (about 90 in five seconds) but zero W/F frames. Browser-Origin, delayed W/F startup, and adjacent reference-client timestamps did not restore paired W/F. Bundled kiwiwfrecorder opened SND and W/F and received SND IQ before the server closed, without clear W/F output. This points to combined external-API stream allocation/association rather than password handling or generic W/F parsing.
Fixture captured: none; standalone frames matched the existing parser and paired W/F returned no payload
Follow-up: compare with a receiver advertising multiple available external API channels; preserve same-timestamp browser-compatible project behavior known to work on the local proxy
```

### 2026-09-07 — requested KX4AZ-T2 proxy diagnosis

```text
Date/time: 2026-09-07T14:11Z UTC
Receiver: kx4az-t2.proxy.kiwisdr.com:8073 (external receiver explicitly requested by user)
Frequency: restored session frequency, approximately 298 kHz
Mode/filter: CW, restored session settings
Stream type: bounded paired SND/W/F, null local sink
Purpose: diagnose receiver register 4 connection failure
Commands sent: normal non-admin paired SND/W/F setup only
Observed behavior: HTTP receiver endpoint returned KiwiSDR 1.902 and current-config controller normalized the stored http:// URL. WebSocket upgrades returned 101, but neither SND nor W/F delivered an initial Kiwi message or W/F frame in repeated five-second bounds. Adding a browser-style Origin header made no difference and was not retained. The bundled reference kiwirecorder also stalled until an external ten-second process timeout, so this is not specific to the new parser or websockets transport. Receiver `/status` reported `users=5`, `users_max=8`, `mode=rx8.wf3`, and `ext_api=4`; receiver-side external-API/W/F availability or policy remains the likely cause despite browser access.
Fixture captured: none because the receiver returned no protocol payload
Follow-up: surface silent-start timeout diagnostics; retry when receiver usage changes or obtain its external-API policy from the operator
```

### 2026-09-05 — integrated receiver switch `.40` to `.41`

```text
Date/time: approximately 2026-09-05T23:18Z / 19:18 local
Receivers: 10.0.0.40:8073 -> 10.0.0.41:8073 via stored register r 2
Frequency: 5000.000 kHz
Mode/filter: AM, -5000..5000 Hz
W/F settings: zoom 7, speed 4, interp 13, 160-row history, 5 Hz presentation cap
Stream type: paired primary SND + W/F; null audio sink
Purpose: Verify integrated console publisher rebinding and fresh W/F after controller-owned receiver restart.
Commands sent: normal paired setup/tune/view/keepalive plus user-level receiver switch; no admin commands.
Observed behavior:
  Automated Kitty remote input first tuned to 5000 kHz, then sent r2.
  Console switched from .40 to .41, replaced/reset W/F history, and resumed rendering.
  At screenshot time status showed receiver 10.0.0.41:8073, SND running, W/F running, 38 source/presented rows, RSSI -96.3 dBm S5.
  Switch-result message reported receiver .41 and restarted playback.
  Console exited normally without a reconnect loop.
Fixture/artifact: docs/screenshots/kiwi-console-switch-41.png; complete fake .40 -> .41 switch regression in tests/harness/test_integrated_terminal.py.
Follow-up: User-attended confirmation and eventual reverse switch; no protocol changes observed.
```

### 2026-09-04 — integrated Kitty console paired W/F

```text
Date/time: 2026-09-04T04:48:36Z..04:48:49Z and 04:49:14Z..04:49:23Z / approximately 00:48..00:49 local
Receiver: 10.0.0.40:8073
Frequency: 5000.000 kHz
Mode: AM
Filter: -5000..5000 Hz
W/F settings: zoom 7, speed 4, interp 13, 300-row history, 5 Hz presentation cap
Stream type: paired primary SND + W/F; null audio sink
Purpose: Validate controller-backed live snapshots in the integrated curses/Kitty console and automated screenshot capture.
Commands sent: normal paired SND/W/F authentication, setup, keepalive, AM tune, and zoom/center commands only; no admin commands.
Observed behavior:
  Both bounded runs exited normally with no reconnect loop.
  First run displayed live frames but stale starting/waiting status.
  Harness-first status synchronization fix called the controller paired-session synchronizer during polling.
  Second run displayed SND running / W/F running and 85 source/presented generations at screenshot time.
  Waterfall image, 4882.8..5117.2 kHz ruler, green 10 kHz passband bracket, and clean lower TUI reservation rendered correctly in Kitty under DWM.
Fixture/artifact: docs/screenshots/kiwi-console-live-local.png; fake paired-operation regression in tests/harness/test_integrated_terminal.py. Existing protocol behavior did not change.
Follow-up: Expand the lower console with existing TUI command/keymap/dashboard behavior and add audio toggle/status controls.
```

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
