# Machine handoff — live/RNA phase

## Branches and release scope

- Primary branch/worktree: `main`, `/home/user/kiwi`; user-approved fast-forward
  merge and operational migration completed 2026-11-10. Nothing was pushed.
- `/home/user/kiwi-rna` remains on `feature/rna-live-logging` as a fallback. Its
  native log/state files are independent copies, not synchronized with main.
- `feature/ndb-analysis-plan` remains preserved at `9e1c96f`, without an active
  worktree. Keep its recorded playback, DSP, practice/review and reports separate.
- Only independent fixes were ported after auditing the 16 analysis-only commits.
  Details, safety references and migration checklist: [merge review](live-phase-merge-review.md).
- Personal logbooks, receiver sites, reports, scripts, preferences and historical
  stages are local operational data, not Git content. Preserve them and screenshots.

## Current capabilities

`kiwi-console` is the primary Kitty/curses receiver interface with paired SND/W/F,
audio, receiver presets/popup, saved radio state, RNA catalogue filtering and
carrier/sideband markers. Inline w/W logging freezes reception evidence; the
advanced editor handles hearing time, not-heard status and audited deletion.

`./logbook` / `kiwi-logbook` is a separate read-only desktop browser for native
SQLite receptions and independently staged WWSU/Kiwi label history. Viewing sources
together does not merge them. Identification and confirmation remain human actions.

The graphical tuning bar preserves RF geometry, shows common NDB search regions,
and leaves waterfall history untouched. The freshness gate honors advertised
acquisition `zoom_cap` independently of coordinate-system `zoom_max`; higher
local display zoom is cropping, not higher FFT resolution.

## Running

Use `/home/user/kiwi` for listening and logging. The migrated private `./rna-listen`
launcher resolves paths relative to itself; `./logbook` reads the migrated sources.
Editable installation now points to this primary worktree. Fallback originals,
external archives, cle material and screenshots were retained unchanged.

Use the installation and general-listening command in [README](../README.md).
For general logging, omit `--log-event CLE332` and use `--no-rna-cle332` to override
saved event filtering. Historical CLE hearings remain unchanged. Console Logged
status is scoped to receiver/event/source; the desktop browser can show all scopes.

Current controls: h/l small steps, H/L large steps, j/k CW bandwidth, n/N station
selection/tune/recenter, v component, y retune, r receiver popup, w update/new draft,
W new hearing, Tab status and Enter save inside inline entry, B/F2 details, Esc
cancel, q quit outside editors. See [user guide](user-guide.md) for full controls.
`./sdr` is the older text TUI launcher, not the RNA-integrated console.

## Receivers and local configuration

Local receivers are 10.0.0.41–43:8073. The operator confirmed all three are at the
same site, but each retains an independent entry in private `rna-sites.toml`.
Never infer other receivers' locations or silently relabel recorded evidence.

Root config.toml enables live operation and disables receiver restriction; inspect
it before deployment elsewhere. Library/generated defaults remain guarded. Do not
connect to public receivers without explicit authorization. Fixtures/dry runs are
the default validation path. No receiver connections were made during merge review.

## Known limitations and validation

The live-phase suite passes 782 tests (776 baseline plus six new regressions).
Compilation, source/installed CLI dry runs, offline terminal logging, logbook
source reading and a clean wheel installation passed; see the merge review. The parked
analysis branch was not merged or retested as part of this release.

Remaining work is in [TODO](../TODO.md): evidence capture, audited desktop editing,
general RNA export, stream deadlines, switch stress, physical-terminal verification
and waterfall cadence. The zoom-cap fix does not settle every 8-channel display
report. Detailed prior live observations remain in [protocol notes](kiwi-protocol.md).

The superseded handoff is preserved in [archive](archive/shared-radio-handoff.md).
