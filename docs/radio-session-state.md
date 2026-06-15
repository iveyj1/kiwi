# Radio session state

This note documents the intended ownership and lifecycle model for interactive receiver and playback handling.

## Why this exists

The interactive client now has several related but distinct moving parts:

- desired radio parameters in `ClientState`
- the receiver currently selected by the user
- the receiver, if any, attached to an active live stream
- one background worker running playback, recording, or capture
- audio sink startup/stop behavior
- live KiwiSDR errors such as busy, bad password, or server down
- TUI status and key handling

A busy receiver exposed a weakness in the implicit lifecycle model: after playback failed, the background worker was no longer running but still held a `play` error. A later receiver-register switch changed receiver state but did not restart playback, leaving no audio and a stale error visible. That case should be treated as a failed playback session with preserved playback intent.

## Ownership rule

The TUI should translate user input into controller actions and render state. It should not own receiver/playback lifecycle policy.

The controller, or a future controller-owned `RadioSessionManager`, should own decisions such as:

- whether a receiver switch should restart playback
- whether a failed playback session should preserve playback intent
- how to stop and join the current worker before switching
- how to rollback if a new receiver fails immediately
- when an operation error is stale and should no longer be displayed as current state

`BackgroundOperation` should remain a low-level single-operation runner. It should not know radio policy.

## State concepts

Keep these concepts distinct:

- `desired_receiver`: receiver selected by the user or restored from state.
- `active_receiver`: receiver attached to the current live stream, if any.
- `desired_playback`: whether the interactive session should keep playback running across recoverable changes.
- `operation_status`: low-level worker status: operation name, running flag, stop request, result, error, metrics.
- `session_error`: current radio-session error. This may be derived from operation status, but stale errors from prior generations should not block current user actions.

## Suggested explicit states

A small explicit state machine is sufficient; no external FSM framework is required.

```text
IDLE
STARTING
PLAYING
STOPPING
FAILED
SWITCHING
RECOVERING
```

Typical transitions:

```text
IDLE -> STARTING -> PLAYING
IDLE -> STARTING -> FAILED
PLAYING -> STOPPING -> IDLE
PLAYING -> SWITCHING -> STARTING -> PLAYING
PLAYING -> SWITCHING -> STARTING -> FAILED -> RECOVERING -> STARTING/PLAYING
FAILED + switch receiver + desired_playback -> STARTING
FAILED + stop -> IDLE
```

## Invariants

- TUI code should not infer lifecycle solely from `background.status().running`.
- Failed playback may still imply `desired_playback = true` for interactive recovery.
- Switching receivers after a failed playback start should start playback on the new receiver when playback intent is preserved.
- `desired_receiver` and `active_receiver` should not be conflated.
- Operation errors should be associated with a session generation or equivalent freshness marker.
- A stale error from receiver A should not remain the current status after receiver B playback starts.
- Receiver switching during active playback should either:
  - stop old playback and start new playback, or
  - report that stopping is still in progress.
- If new receiver playback fails immediately during a switch from active playback, the controller should rollback to the previous receiver and attempt to restore playback when appropriate.

## Current implementation status

Current code uses `BackgroundOperation` plus a controller-owned `RadioSessionState` snapshot. Receiver-register switching delegates lifecycle policy to `ClientController.switch_receiver()` instead of having the TUI infer policy from raw worker status. Recent fixes cover important cases with harness tests:

- URL-like receiver addresses are normalized to `host:port`.
- Active playback receiver switching stops and restarts playback.
- Immediate busy failure during active switch restores the previous receiver.
- Switching receivers after failed playback starts playback on the new receiver and clears/replaces the stale error.

The next architectural step is to grow this into a small `RadioSessionManager` if additional lifecycle operations need the same policy, such as crossfade, reconnect/retry, or simultaneous playback/recording/detection consumers.

## Regression cases to preserve

- Idle `r <register>` changes receiver without starting playback.
- Active playback `r <register>` stops old playback and restarts on the selected receiver.
- Active playback switch to a busy receiver restores the previous receiver and reports the new failure.
- Failed playback on a busy receiver followed by `r <register>` starts playback on the selected receiver.
- Stored URL receivers such as `http://host:8073/` normalize to `host:8073`.
- Stale errors from old sessions are not shown as current after a successful new playback session.

## Relation to future work

A controller-owned session manager also prepares the design for:

- bumpless receiver transfer and crossfade
- clearer startup playback behavior
- explicit reconnect/retry policy, if added later
- simultaneous playback/recording/detection consumers
- richer dashboard state, including desired vs active receiver
