# TODO

## Current slice

Goal: Add interactive command aliases, then build keymap/command-mode TUI support, configurable keymaps, and tune/volume step actions.

Done criteria:

- Slice 1: add command aliases (`?` for status, `re`, `tu`, `mo`, `fi`, `du`, `fr`, `pb`, `rb`, `cb`, `sp`, `he`, `q`, `qu`) with tests.
- Slice 2: add two-mode TUI input: keymap mode by default, `:` command mode, enter/escape behavior, and command history up/down.
- Slice 3: add TOML configuration defaults for keymaps and step sizes.
- Slice 4: add tune-step and volume/volume-step actions wired to keymaps.

Test command: `python3 -m pytest tests/harness tests/audio tests/protocol`

Live-radio needed: no; harness-first UI/controller work.

Docs to update: `docs/roadmap.md`, `docs/user-guide.md`, `docs/dev-log.md`

## Next

- Inspect `kiwiclient/` and identify SND/audio connection path.
- Define fixture format for KiwiSDR control and stream messages.
- Add first parser test using synthetic or captured SND data.
- Add first local live-radio capture only after the harness path exists.

## Later

- Basic desktop client: connect, tune, mode, audio.
- Waterfall decode and rendering.
- Recording pipeline.
- MF/LF beacon detector.
- Long-integration/correlation analysis.
