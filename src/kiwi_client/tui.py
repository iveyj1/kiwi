"""Minimal terminal UI for the KiwiSDR client shell.

The renderer is pure/testable. The curses runner is intentionally thin and uses
ClientController commands so it does not duplicate protocol/audio behavior.
"""

from __future__ import annotations

import argparse
import curses
from dataclasses import dataclass, field, replace
from enum import Enum
from typing import Any

from pathlib import Path

from kiwi_client.client_app import ClientCommandError, ClientController, ClientState, available_commands
from kiwi_client.config import KiwiClientConfig, load_config


class InputMode(Enum):
    """TUI input modes."""

    KEYMAP = "keymap"
    COMMAND = "command"


@dataclass
class TuiInputState:
    """Mutable command/keymap input state for the curses runner."""

    mode: InputMode = InputMode.KEYMAP
    command: str = ""
    history: list[str] = field(default_factory=list)
    history_index: int | None = None


@dataclass(frozen=True)
class DashboardModel:
    """Data needed to render the basic client dashboard."""

    state: ClientState
    last_response: dict[str, Any] | None = None
    message: str = ""


def render_dashboard(
    state: ClientState,
    last_response: dict[str, Any] | None = None,
    *,
    message: str = "",
    operation: dict[str, Any] | None = None,
) -> str:
    """Render a text dashboard for tests and curses display."""
    lines = [
        "KiwiSDR Client",
        "==============",
        f"Receiver: {state.receiver}",
        f"Connected: {'yes' if state.connected else 'no'}",
        f"Frequency: {state.frequency_khz:.3f} kHz",
        f"Mode/filter: {state.mode} {state.low_cut_hz}..{state.high_cut_hz} Hz",
        f"Volume: {state.volume_percent}%",
        f"Live limits: {state.duration_seconds:g}s / {state.max_frames} SND frames",
        "",
        "Commands: status, receiver, tune, mode, filter, duration, frames, play-bg, record-bg, capture-bg, stop, help, quit",
    ]
    if operation is not None:
        lines.extend([
            "",
            f"Operation: {operation.get('name') or 'none'}",
            f"Running: {'yes' if operation.get('running') else 'no'}",
            f"Stop requested: {'yes' if operation.get('stop_requested') else 'no'}",
            f"Elapsed: {operation.get('elapsed_seconds', 0.0):.1f}s",
        ])
        metrics = operation.get("metrics") or {}
        if metrics:
            rssi = metrics.get("rssi_db")
            smeter = metrics.get("smeter")
            frames = metrics.get("snd_frames")
            if rssi is not None and smeter is not None:
                lines.append(f"RSSI/S-meter: {rssi:.1f} dB / {smeter}")
            if frames is not None:
                lines.append(f"SND frames: {frames}")
            sample_rate = metrics.get("sample_rate_hz")
            if sample_rate is not None:
                lines.append(f"Sample rate: {sample_rate} Hz")
            sequence_gaps = metrics.get("sequence_gaps")
            if sequence_gaps is not None:
                lines.append(f"Sequence gaps: {sequence_gaps}")
            adc_overflows = metrics.get("adc_overflows")
            if adc_overflows is not None:
                lines.append(f"ADC overflows: {adc_overflows}")
        if operation.get("result"):
            lines.append(f"Operation result: {operation['result']}")
        if operation.get("error"):
            lines.append(f"Operation error: {operation['error']}")
    if last_response is not None:
        lines.extend(["", f"Last response: {last_response.get('type', 'unknown')}"])
        if "active_command" in last_response:
            lines.append(f"Applied to active stream: {last_response['active_command']}")
        if "result" in last_response:
            lines.append(f"Result: {last_response['result']}")
        if "plan" in last_response:
            lines.append(f"Plan: {last_response['plan']}")
    if message:
        lines.extend(["", f"Message: {message}"])
    return "\n".join(lines)


def normalize_key_name(ch: int) -> str | None:
    """Return a config key name for a curses key code."""
    special = {
        curses.KEY_RIGHT: "right",
        curses.KEY_LEFT: "left",
        curses.KEY_UP: "up",
        curses.KEY_DOWN: "down",
    }
    if getattr(curses, "KEY_SRIGHT", None) is not None:
        special[curses.KEY_SRIGHT] = "shift-right"
    if getattr(curses, "KEY_SLEFT", None) is not None:
        special[curses.KEY_SLEFT] = "shift-left"
    if ch in special:
        return special[ch]
    if 1 <= ch <= 26:
        return f"ctrl-{chr(ch + 96)}"
    if 0 <= ch < 256:
        char = chr(ch)
        if char.isalpha() and char.isupper():
            return f"shift-{char.lower()}"
        return char
    return None


def expand_key_action(action: str, controller: ClientController, config: KiwiClientConfig) -> str:
    """Expand configured key actions into controller commands."""
    parts = action.split()
    if len(parts) == 2 and parts[0] == "tune-step":
        sign = -1 if parts[1].startswith("-") else 1
        token = parts[1].lstrip("+-")
        step_hz = {
            "small": config.steps.small_hz,
            "medium": config.steps.medium_hz,
            "large": config.steps.large_hz,
        }.get(token)
        if step_hz is not None:
            new_frequency = controller.state.frequency_khz + sign * step_hz / 1000.0
            return f"tune {new_frequency:.3f}"
    if len(parts) == 2 and parts[0] == "volume-step" and parts[1] in {"+10", "-10"}:
        sign = -1 if parts[1].startswith("-") else 1
        return f"volume-step {sign * config.volume.step_percent}"
    return action


def request_tui_quit(controller: ClientController, *, join_timeout: float = 2.0) -> tuple[dict[str, Any] | None, str]:
    """Safely quit the TUI, stopping any active background operation first."""
    status = controller.background.status()
    if status.running:
        controller.background.stop()
        final = controller.background.join(timeout=join_timeout)
        if final.running:
            return {"type": "operation-status", "operation": final.as_dict()}, "Stopping background operation before quit..."
        controller.running = False
        return {"type": "operation-status", "operation": final.as_dict()}, "Stopped background operation and quitting."
    controller.running = False
    return {"type": "quit"}, ""


def handle_tui_key(
    ch: int,
    input_state: TuiInputState,
    controller: ClientController,
    config: KiwiClientConfig | None = None,
) -> tuple[dict[str, Any] | None, str | None]:
    """Handle one curses key and return an optional response/message."""
    config = config or load_config()
    if input_state.mode == InputMode.KEYMAP:
        key_name = normalize_key_name(ch)
        action = config.keys.get(key_name) if key_name is not None else None
        if action == "command-mode" or ch == ord(":"):
            input_state.mode = InputMode.COMMAND
            input_state.command = ""
            input_state.history_index = None
            return None, ""
        if action:
            if action == "quit":
                return request_tui_quit(controller)
            try:
                return controller.execute(expand_key_action(action, controller, config)), ""
            except ClientCommandError as exc:
                return None, f"error: {exc}"
        return None, None

    if ch in (27,):
        input_state.mode = InputMode.KEYMAP
        input_state.command = ""
        input_state.history_index = None
        return None, ""
    if ch in (curses.KEY_BACKSPACE, 127, 8):
        input_state.command = input_state.command[:-1]
        input_state.history_index = None
        return None, None
    if ch == curses.KEY_UP:
        if input_state.history:
            if input_state.history_index is None:
                input_state.history_index = len(input_state.history) - 1
            else:
                input_state.history_index = max(0, input_state.history_index - 1)
            input_state.command = input_state.history[input_state.history_index]
        return None, None
    if ch == curses.KEY_DOWN:
        if input_state.history and input_state.history_index is not None:
            if input_state.history_index >= len(input_state.history) - 1:
                input_state.history_index = None
                input_state.command = ""
            else:
                input_state.history_index += 1
                input_state.command = input_state.history[input_state.history_index]
        return None, None
    if ch in (10, 13):
        command = input_state.command.strip()
        input_state.command = ""
        input_state.history_index = None
        input_state.mode = InputMode.KEYMAP
        if not command:
            return None, ""
        input_state.history.append(command)
        if command == "help":
            return {"type": "help", "commands": available_commands()}, ""
        if command.lower() in {"quit", "exit", "q", "qu"}:
            return request_tui_quit(controller)
        try:
            return controller.execute(command), ""
        except ClientCommandError as exc:
            return None, f"error: {exc}"
    if 0 <= ch < 256:
        input_state.command += chr(ch)
        input_state.history_index = None
    return None, None


def state_from_config(config: KiwiClientConfig, state: ClientState | None = None) -> ClientState:
    """Return client state with live limits and receiver policy from config."""
    state = state or ClientState()
    return replace(
        state,
        duration_seconds=config.live.duration_seconds,
        max_frames=config.live.max_frames,
        receivers_restricted=config.receivers.restricted,
        allowed_receivers=config.receivers.allowed,
    )


def run_tui(controller: ClientController | None = None, *, config: KiwiClientConfig | None = None) -> None:
    """Run a small curses command UI."""
    config = config or load_config()
    controller = controller or ClientController(state=state_from_config(config), allow_live_default=config.live.allow_live)
    if controller is not None:
        controller.allow_live_default = config.live.allow_live
        controller.state = state_from_config(config, controller.state)
    curses.wrapper(_run_curses, controller, config)


def build_arg_parser() -> argparse.ArgumentParser:
    """Build the TUI CLI argument parser."""
    parser = argparse.ArgumentParser(description="KiwiSDR curses TUI")
    parser.add_argument("--config", type=Path, help="optional TOML configuration file")
    return parser


def main(argv: list[str] | None = None) -> int:
    """CLI entrypoint for the curses TUI."""
    parser = build_arg_parser()
    args = parser.parse_args(argv)
    config = load_config(args.config)
    run_tui(ClientController(state=state_from_config(config), allow_live_default=config.live.allow_live), config=config)
    return 0


def _run_curses(stdscr, controller: ClientController, config: KiwiClientConfig) -> None:
    curses.curs_set(1)
    stdscr.timeout(250)
    last_response: dict[str, Any] | None = None
    message = "Keymap mode. Press ':' for commands. Use explicit --allow-live for live operations."
    input_state = TuiInputState()

    while controller.running:
        stdscr.erase()
        dashboard = render_dashboard(
            controller.state,
            last_response,
            message=message,
            operation=controller.background.status().as_dict(),
        )
        height, width = stdscr.getmaxyx()
        for row, line in enumerate(dashboard.splitlines()[: max(0, height - 3)]):
            stdscr.addnstr(row, 0, line, max(0, width - 1))
        prompt = ":" if input_state.mode == InputMode.COMMAND else "keymap (: command)> "
        stdscr.addnstr(height - 2, 0, prompt + input_state.command, max(0, width - 1))
        stdscr.refresh()

        ch = stdscr.getch()
        if ch == -1:
            continue
        response, new_message = handle_tui_key(ch, input_state, controller, config)
        if response is not None:
            last_response = response
        if new_message is not None:
            message = new_message


if __name__ == "__main__":
    raise SystemExit(main())
