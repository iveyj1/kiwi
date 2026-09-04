# Shared session and UI integration plan

## Decision

Use an integrated Kitty terminal interface as the primary near-term UI: a reserved waterfall region above curses-owned rulers, presets, status, controls, command entry, and logs. Retain standalone `kiwi-tui` and `kiwi-wf-terminal` as lightweight diagnostics/fallbacks, and retain PySide6 only as an optional prototype.

Kitty is the initial attended target because it is installed and provides the canonical graphics-protocol implementation. Keep the graphics boundary compatible with Ghostty/WezTerm where practical. Receiver lifecycle and command ownership remain below every frontend; curses owns integrated input/layout while terminal image generation stays renderer-neutral.

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
    +-- integrated Kitty UI: primary waterfall, rulers, presets, controls, status
    +-- kiwi-tui: controls, status, diagnostics, fallback
    +-- kiwi-wf-terminal: standalone Kitty raster fallback
    +-- kiwi-gui: optional native prototype
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

Status: **Foundation and initial ClientController adapter implemented; live lifecycle migration remains.**

`src/kiwi_client/session_manager.py` defines immutable paired-session snapshots, generation-tagged errors, typed lifecycle/control actions, and deterministic SND/W/F command routing. It is UI-neutral and harness-covered. `ClientController` initializes and synchronizes shared receiver/frequency/mode/passband/CW/precision state while retaining legacy `RadioSessionState` responses. Live `BackgroundOperation` lifecycle and terminal-viewer selection state still need migration before this layer owns live policy.

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

Status: **Headless paired operation implemented; embedded graphics not enabled.**

Current audio-only `BackgroundOperation` playback is represented as generation-aware SND running/stopping/failed state with W/F explicitly inactive. `radio-bg` starts a headless paired SND/W/F worker through the shared coordinator, routes stream-tagged commands, publishes filtered W/F metadata/metrics, and restarts the pair on receiver switch. The pure dashboard displays desired/active receiver, SND/W/F states, audio state, and zoom while legacy operation details remain available.

Add paired-session lifecycle and status to `kiwi-tui` without embedding graphics first.

- Start/stop the shared interactive session.
- Display SND/W/F states, receiver, tuned/selected frequency, zoom, audio state, and current errors.
- Route existing tune/mode/filter/receiver/preset actions through the session manager.
- Preserve command mode and direct `:tune <kHz>` operation.
- Ensure receiver switching restarts the pair and handles rollback/stale errors.

## Phase 4 — Graphical frontend decision and prototype

Status: **PySide6 fixture prototype implemented and evaluated; deprioritized after attended use.**

`WaterfallSnapshotPublisher` retains bounded immutable numeric rows with per-row frequency coordinates and monotonic arrival times. Consumers request the latest generation, so a slow GUI skips superseded display states without creating a queue. Headless comparison found both PySide6 and pygame-ce comfortably exceed the 20 FPS direct-RGB target. PySide6 Essentials is larger but was selected for its mature desktop controls/layout/input support. `kiwi-gui` now displays static or timer-driven fixture history through direct `QImage`/`QPixmap` presentation. Its incremental rasterizer colors only newly presented rows, consumes the latest snapshot generation, and reports source/presentation generations. Fixture-only tuned/passband/selection overlays and keyboard/widget controls dispatch through `RadioSessionManager`; generated commands are intentionally not sent. Live session integration remains pending. Benchmark details are in [Native GUI toolkit benchmark plan](native-gui-benchmark.md).

The prototype validated snapshot/raster/input boundaries but did not provide a convincing primary workflow. Those reusable boundaries now feed the integrated terminal direction.

Prototype requirements:

- consume renderer-neutral waterfall snapshots,
- display RGB data without PNG/base64 terminal transfer,
- maintain approximately 20 FPS when source cadence permits,
- support resize, mouse selection, direct frequency entry, zoom, overlays, and audio controls,
- preserve fixture/fake-session operation without network access.

Toolkit comparison is complete; no further native integration is planned before the Kitty terminal slice is evaluated.

## Phase 5 — Integrated curses-aware Kitty pane

Status: **Fixture-only integrated shell implemented; attended Kitty validation pending.**

Requirements:

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
