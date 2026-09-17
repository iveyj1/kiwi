# Machine handoff

## Repository and merge preparation

- Working branch: `feature/shared-radio-session`.
- User direction: clean up and prepare for merge into `main`; do not execute the merge yet.
- The former `wf1` workflow is superseded. At preparation time, local `main` is an ancestor of this feature branch (55 commits behind before cleanup commits).
- Keep `kiwisdr-screenshot.png` untracked and unchanged. `state.json` is ignored local session state.
- Do not commit forum credentials, session cookies, or downloaded authenticated pages.

## Current capabilities

`kiwi-console` is the primary integrated Kitty waterfall/TUI. It uses controller-owned paired SND/W/F, bounded history, double-buffered presentation, runtime audio gating, mode/passband controls, preset/receiver registers, and saved state. The native GUI remains an optional prototype; standalone CLI tools remain available.

The headless paired path fetches `/VER` once, uses its timestamp in `/ws/kiwi/<ts>/<stream>`, and waits for SND `badp=0` before opening W/F. A stalled audio stop-fade no longer waits indefinitely for new samples; the primary task has a cooperative-stop cancellation fallback. This does not prove every possible transport or audio-device hang is resolved.

## Local receivers

| Register | Address | Role |
|---|---|---|
| `r1` | `10.0.0.41:8073` | General default |
| `r2` | `10.0.0.42:8073` | Alternative |
| `r3` | `10.0.0.43:8073` | Preferred NDB development target; user reports 4-channel mode |

Public receivers will commonly be in 8-channel mode according to the user. Reduced zoom and cadence must not prevent audio/signal analysis. Exact mode-dependent zoom limits remain to be verified from receiver metadata; do not hardcode the reported approximate 11/14 distinction.

Root `config.toml` intentionally has live operation enabled and receiver restriction disabled. Library/generated defaults remain guarded. Review that local configuration before using it on another machine. Public receiver testing still requires explicit user authorization.

## Setup and demo

```bash
./setup-python
source .kiwi-venv/bin/activate
python -m pytest -q
```

Explicit local NDB-development target (restored frequency/mode still apply):

```bash
kiwi-console --allow-live --receiver 10.0.0.43:8073 \
    --config config.toml --rows 300 --refresh-hz 5 --auto-scale
```

Console controls: `h/l` or Left/Right tune; `H/L` fine tune; Up/Page Up and Down/Page Down tune by one visible span; `f` enters frequency and recenters only when offscreen; `c` centers; `+/-` zoom; `a` toggles audio; `k/j` volume; `m` selects mode; `r` selects receiver; `q` exits.

## Outstanding work

- First-message/first-frame/stall diagnostics and rapid-switch stress coverage. One unreproduced hang remains reported after the teardown fix.
- Audit bootstrap, guardrails, and cancellation across all frontends.
- Audit `zoom_max`/`zoom_cap` propagation for mode-dependent receivers.
- Optional presentation-cadence improvement and short bounded W/F buffer; not part of this merge preparation.
- SND/IQ fan-out into recording/detection; fixture-first NDB detector and later long-term integration. W/F is an overview, not the analysis data source.

Validation results are recorded in `docs/dev-log.md`; current work is tracked in `TODO.md`. Historical captures retain their original addresses.
