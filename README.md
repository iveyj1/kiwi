# KiwiSDR live receiver and RNA logbook

Local KiwiSDR desktop/terminal clients with a fixture-first test harness. This
phase provides live audio/waterfall operation, RNA catalogue navigation, audited
reception logging and a standalone historical log browser. Experimental recorded
playback and signal-analysis workflows remain on `feature/ndb-analysis-plan`.

## Setup

Python 3.11 or newer; Kitty for the integrated graphical terminal. Audio playback
also requires a working PortAudio installation/device.

```bash
python3 -m venv .kiwi-venv
source .kiwi-venv/bin/activate
python -m pip install -e '.[dev,live,playback,terminal-graphics]'
# Optional standalone Qt logbook/native GUI:
python -m pip install -e '.[gui-pyside]'
```

Run commands from the repository root so catalogue, state and log paths resolve
consistently. If reusing an environment from another branch, reinstall the editable
package to refresh its entry points. For an uninstalled source checkout, use
`PYTHONPATH=src python -m kiwi_client.integrated_terminal` instead of `kiwi-console`.

## General NDB listening

Create a private `rna-sites.toml` using `docs/rna-sites.example.toml` as a format
example, replacing its example coordinates with actual locations. Sites are
independent per receiver address. Then, for deliberate local listening:

```bash
kiwi-console --allow-live --receiver 10.0.0.41:8073 --audio \
  --rna rna-signals.csv --rna-sites rna-sites.toml \
  --logbook receptions.sqlite --no-rna-cle332
```

Omit `--log-event` for general listening. Existing CLE-tagged hearings remain in
the same database. `--no-rna-cle332` disables any saved CLE catalogue restriction;
other saved filters still apply. Do not use a personal CLE launcher unchanged.

- `/`: search; n/N: select, tune and center; v: carrier/sideband/stored component.
- h/l: small steps; H/L: large steps; j/k: CW bandwidth; r: receiver popup.
- w: inline update/latest hearing or new draft; W: always a new hearing.
- In inline entry: Tab confirmed/tentative, Enter save, Esc cancel; F2 details.
- B: detailed log editor; q: quit outside editors.

The catalogue and shaded frequency regions are navigation aids, not detections.
The console's Logged status is scoped to receiver/event/source.

## Browse logs without connecting

```bash
./logbook
./logbook --native-only
```

The browser is read-only. Native receptions, WWSU review stages and Kiwi label
history stay separate. Standalone editing and general RNA submission export are
not implemented; the existing dedicated report exporter is for CLE332.

## Offline validation

```bash
python -m pytest -q
python -m compileall -q src
kiwi-console --fixture tests/fixtures/kiwi/local-wf-am-855-zoom7.jsonl --dry-run
```

No radio connection is needed. Optional GUI tests require the Qt extra.

## Documentation

- [User guide](docs/user-guide.md): controls, settings, logging and source provenance.
- [Current handoff](docs/handoff.md) and [TODO](TODO.md).
- [Live-phase merge review](docs/live-phase-merge-review.md): audit, tests and safe migration.
- [Architecture](docs/architecture.md), [protocol](docs/kiwi-protocol.md),
  [harness](docs/harness.md) and [NDB techniques](docs/ndb-techniques.md).

`./sdr` launches the older text TUI, not the integrated RNA interface. Personal
launchers/configuration may differ; inspect them rather than assuming identical
screens. Keep private logs, historical inputs, receiver sites and state out of Git.
