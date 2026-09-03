# Shared session and UI integration plan

## Decision

Retain `kiwi-tui` as a lightweight control, diagnostics, and fallback interface. Keep `kiwi-wf-terminal` as the current terminal raster viewer. Do not make curses the primary graphical architecture.

Move receiver lifecycle and command ownership below both interfaces, then add a native graphical frontend that consumes the same controller/session APIs. A curses-aware Kitty pane remains optional after shared session ownership is complete; it must not drive protocol or lifecycle design.

## Target architecture

```text
ClientController
    |
    +-- RadioSessionManager
          |
          +-- primary SND session
          |     +-- audio output
          |     +-- future recorder/detector consumers
          |
          +-- paired W/F session
                +-- numeric/RGB history
                +-- frame/state snapshots

Frontends
    +-- kiwi-tui: controls, status, diagnostics, fallback
    +-- kiwi-wf-terminal: Kitty raster frontend
    +-- future native GUI: primary integrated audio/waterfall frontend
```

## Invariants

- Assign one session timestamp to paired SND and W/F transports.
- Open and authenticate primary SND before opening W/F.
- Keep transport, protocol, state, rendering, and UI separable and harness-testable.
- The controller/session layer owns desired and active receiver state, restart/rollback policy, and command routing.
- Frontends submit typed actions; they do not independently construct lifecycle policy.
- Receiver switching stops/restarts the paired session as one user operation.
- Network receive must never block on image generation or terminal/native rendering.
- Audio, W/F, renderer, and future consumer errors remain independently observable where possible.
- No duplicate SND connection is required merely to show a second frontend.

## Phase 1 — Shared paired-session coordinator

Status: **Done for the existing combined terminal session.**

`src/kiwi_client/paired_session.py` now owns shared timestamp resolution plus SND-first/W/F-second startup, shared stop ownership, independent command queues, readiness, and cleanup. `kiwi-wf-terminal` uses it while retaining terminal-specific rendering, input, and audio status presentation.

Extract SND-first/W/F-second startup, shared stop ownership, independent command queues, readiness, status, and error isolation from `waterfall_terminal.py` into a UI-neutral module.

Done criteria:

- Pure fake-runner tests prove SND readiness precedes W/F startup.
- SND failure before readiness prevents orphan W/F startup.
- W/F completion/failure stops the paired SND task cleanly.
- SND failure after readiness is reported without corrupting W/F state.
- Separate SND and W/F command queues remain available.
- `kiwi-wf-terminal` uses the shared coordinator with no user-visible regression.

## Phase 2 — Controller session manager

Status: **Foundation implemented; controller migration remains.**

`src/kiwi_client/session_manager.py` defines immutable paired-session snapshots, generation-tagged errors, typed lifecycle/control actions, and deterministic SND/W/F command routing. It is UI-neutral and harness-covered. Existing `ClientController` and terminal-viewer state still need adapters/migration before this layer owns live policy.

Introduce a controller-owned `RadioSessionManager` around the paired coordinator.

Responsibilities:

- desired/active receiver and generation,
- desired playback and mute state,
- frequency/mode/passband/CW offset,
- W/F center/zoom and selected frequency,
- start/stop/switch/recovery policy,
- immutable status and metrics snapshots,
- typed tune, recenter, zoom, audio, and direct-frequency actions.

Migrate standalone viewer and TUI actions to the same command API. Preserve existing `BackgroundOperation` for finite capture/record jobs until SND consumer fan-out exists.

## Phase 3 — TUI integration

Add paired-session lifecycle and status to `kiwi-tui` without embedding graphics first.

- Start/stop the shared interactive session.
- Display SND/W/F states, receiver, tuned/selected frequency, zoom, audio state, and current errors.
- Route existing tune/mode/filter/receiver/preset actions through the session manager.
- Preserve command mode and direct `:tune <kHz>` operation.
- Ensure receiver switching restarts the pair and handles rollback/stale errors.

## Phase 4 — Graphical frontend decision and prototype

Prefer a native raster prototype over coupling the main product to curses plus terminal graphics.

Prototype requirements:

- consume renderer-neutral waterfall snapshots,
- display RGB data without PNG/base64 terminal transfer,
- maintain approximately 20 FPS when source cadence permits,
- support resize, mouse selection, direct frequency entry, zoom, overlays, and audio controls,
- preserve fixture/fake-session operation without network access.

Choose a toolkit only after a small benchmark/prototype compares dependency size, image update cost, input handling, packaging, and Linux desktop behavior.

## Optional phase — Curses-aware Kitty pane

Only if terminal integration remains valuable after the native direction is evaluated:

- curses owns layout and keyboard input,
- an integrated backend places Kitty graphics inside a curses-reserved rectangle,
- PNG work stays off-thread but terminal writes occur on the UI thread,
- resize and alternate-screen cleanup are deterministic,
- unsupported terminals retain a text/status fallback.

## Later — SND consumer fan-out

Decode one SND stream and distribute samples to independently managed consumers:

- local playback,
- WAV recording,
- beacon detector,
- later long-integration analysis.

Each consumer requires bounded buffering and explicit overflow/latency policy. Do not open duplicate SND sockets solely to add consumers.

## Validation policy

Each phase is harness-first. Use fake SND/W/F runners and fixture-backed frames before attended local-radio tests. External receivers are never used automatically.
