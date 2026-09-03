# Machine handoff

## Repository state

- Integration branch: `wf1`
- `main` is closed and must remain untouched until the user changes the workflow.
- Implementation work uses short-lived feature branches merged into `wf1`.
- Latest completed work: combined Kitty raster waterfall plus paired SND audio.
- Last full harness: 280 tests passed.

## Validated behavior

User validation on `misdr.proxy.kiwisdr.com:8073` confirmed combined audible SND and W/F operation after matching Kiwi browser session behavior:

1. Assign one shared session timestamp.
2. Open and authenticate primary SND first.
3. Open paired W/F second.
4. Keep SND connected while local audio output is muted; `a` toggles the lazy output sink.

The working local defaults are 5000 kHz AM, passband -5000..5000 Hz, W/F zoom 7, speed 4, interp 13.

## Standalone viewer controls

- `h` / `l`, arrows: active configured main frequency step.
- `H` / `L`, shifted arrows: active configured small step.
- `t` / `T`: cycle mode step pairs.
- `0`: reset exact cursor to tuned frequency on the active round grid.
- `c`: recenter W/F on exact cursor frequency.
- `+` / `=` / `-`: bounded zoom around cursor.
- `a`: mute/enable local audio output without tearing down primary SND.
- Enter: send exact cursor tune to SND using mode, passband, command precision, and CW offset.
- `q`: clean coordinated shutdown.

## Configuration note

Root `config.toml` currently has `[receivers].restricted = false` and includes:

- `10.0.0.40:8073`
- `10.0.0.41:8073`
- `10.0.0.42:8073`
- `misdr.proxy.kiwisdr.com:8073`

Set `restricted = true` if only explicitly listed receivers should be accepted.

## Setup on another machine

```bash
git clone git@github.com:iveyj1/kiwi.git kiwi-openai
cd kiwi-openai
git switch wf1
./setup-python
source .kiwi-venv/bin/activate
python -m pytest -q
```

Typical run:

```bash
kiwi-wf-terminal --allow-live --host misdr.proxy.kiwisdr.com --audio
```

Do not automatically test against external/public receivers. Use external receivers only when explicitly requested by the user. Local project receivers remain `10.0.0.40:8073` and `10.0.0.41:8073`.

## Next work

- Evaluate combined mute/tune/recenter/zoom behavior during longer normal use.
- Refine compact status and keyboard-help presentation if truncation is inconvenient.
- Add timing diagnostics only if temporal jumps become problematic; current jumps resemble Kiwi browser behavior.
- Decide whether to retain the standalone companion viewer or move toward integrated/native display.

Detailed history is in `docs/dev-log.md`, protocol evidence in `docs/kiwi-protocol.md`, and current planning in `TODO.md`.
