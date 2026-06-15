# Architecture

## Main design

```text
Desktop UI
    |
Controller / Application State
    |
Receiver Client API
    |
+----------------------+----------------------+------------------+
| Kiwi Transport       | Protocol Parser      | Command Encoder  |
+----------------------+----------------------+------------------+
           |
           +--> Audio Pipeline --> Audio Output / Recorder / Detector
           |
           +--> Waterfall Pipeline --> Waterfall Model --> Renderer
           |
           +--> Status / S-meter / Metadata
```

## Rule

Protocol handling must be usable without the desktop UI.

Interactive receiver/playback lifecycle policy belongs in the controller layer, not in the TUI. See [Radio session state](radio-session-state.md) for the desired explicit session-state model around receiver switching, background playback, stale errors, and future bumpless transfer work.

## Suggested modules

```text
kiwi_transport
    WebSocket/session handling.

kiwi_protocol
    Frame parsing, command encoding, message types, units.

receiver_model
    Current frequency, mode, filter, status, S-meter, stream state.

audio
    Sample conversion, buffering, playback, recording.

waterfall
    Frame conversion, scaling, rendering model.

detectors
    MF/LF beacon detection and later long-integration analysis.

harness
    Fixture replay, synthetic frame generation, fake receiver server.

app
    Desktop UI shell.
```

## Dependency direction

```text
app -> receiver_model -> kiwi_protocol -> kiwi_transport
app -> audio
app -> waterfall
detectors -> audio/recording data
tests -> harness -> protocol/audio/waterfall/detectors
```

Avoid dependencies in the reverse direction.

## Non-goals for early milestones

- Large plugin framework
- Multi-user server architecture
- Public receiver crawling
- Complex database schema
- Automated unattended live-radio testing
