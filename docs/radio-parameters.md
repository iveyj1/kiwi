# Radio parameters

Concise list of radio/client parameters currently settable or persisted by this project.

## Receiver/session

- `receiver` / `host` / `port` — KiwiSDR receiver address.
- `user` — Kiwi user/identity string sent as `SET ident_user=...`.
- `duration_seconds` — live operation duration limit; `0` means unlimited.
- `max_frames` — live SND/W/F frame limit; `0` means unlimited.
- `receivers_restricted` — restrict live connections to configured allowlist.
- `allowed_receivers` — allowed receiver addresses.

## Tuning and demodulation

- `frequency_khz` — tuned frequency in kHz.
- `mode` — demodulation mode, e.g. `am`, `usb`, `lsb`, `cw`, `iq` as supported by KiwiSDR.
- `low_cut_hz` — low passband edge in Hz.
- `high_cut_hz` — high passband edge in Hz.

Kiwi command shape:

```text
SET mod=<mode> low_cut=<Hz> high_cut=<Hz> freq=<kHz>
```

## AGC

- `agc_on` — AGC enabled/disabled.
- `agc_hang` — AGC hang enabled/disabled.
- `agc_threshold` — AGC threshold.
- `agc_slope` — AGC slope.
- `agc_decay_ms` — AGC decay time.
- `agc_gain` — manual gain.

Kiwi command shape:

```text
SET agc=<0|1> hang=<0|1> thresh=<value> slope=<value> decay=<ms> manGain=<value>
```

## Audio/playback local settings

- `volume_percent` — local system output volume target.
- `audio_startup_mute_ms` — decoded PCM dropped after playback start.
- `audio_startup_fade_in_ms` — fade-in after startup mute/drop.
- `audio_stop_fade_out_ms` — cooperative stop fade-out.

## Waterfall settings

- `center_khz` — W/F center frequency for standalone W/F capture/preview.
- `zoom` — W/F zoom level.
- `maxdb` — W/F display/capture max dB scale.
- `mindb` — W/F display/capture min dB scale.
- `speed` — W/F update speed, currently `1..4`.
- `interp` — W/F interpolation/compensation setting.
- `compression` / `wf_comp` — W/F compression flag; first parser path uses `0` only.

Kiwi command shapes:

```text
SET zoom=<zoom> cf=<center_khz>
SET maxdb=<maxdb> mindb=<mindb>
SET wf_speed=<1..4>
SET wf_comp=<0|1>
SET interp=<value>
```

## Preset scopes

Minimal preset currently stores:

- `host`
- `port`
- `frequency_khz`
- `mode`
- `low_cut_hz`
- `high_cut_hz`

Full preset currently stores all `ClientState` fields, including runtime/client settings.

Persistence layout:

- `config.toml` holds durable configuration, including `[receivers].allowed` and `[presets].file`.
- `presets.toml` holds durable `[radio_presets.<register>]` and `[receiver_presets.<register>]` tables.
- `state.json` holds ephemeral `last_state` only. It does not hold presets, receiver presets, or config-owned fields such as `allowed_receivers`, audio fade settings, or live limits.
