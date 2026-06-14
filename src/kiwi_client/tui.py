"""Minimal terminal UI for the KiwiSDR client shell.

The renderer is pure/testable. The curses runner is intentionally thin and uses
ClientController commands so it does not duplicate protocol/audio behavior.
"""

from __future__ import annotations

import curses
from dataclasses import dataclass
from typing import Any

from kiwi_client.client_app import ClientCommandError, ClientController, ClientState, available_commands


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


def run_tui(controller: ClientController | None = None) -> None:
    """Run a small curses command UI."""
    controller = controller or ClientController()
    curses.wrapper(_run_curses, controller)


def main(argv: list[str] | None = None) -> int:
    """CLI entrypoint for the curses TUI."""
    run_tui(ClientController())
    return 0


def _run_curses(stdscr, controller: ClientController) -> None:
    curses.curs_set(1)
    stdscr.timeout(250)
    last_response: dict[str, Any] | None = None
    message = "Type 'help' for commands. Use explicit --allow-live for live operations."
    command = ""

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
        prompt = "kiwi> "
        stdscr.addnstr(height - 2, 0, prompt + command, max(0, width - 1))
        stdscr.refresh()

        ch = stdscr.getch()
        if ch == -1:
            continue
        if ch in (10, 13):
            try:
                if command.strip() == "help":
                    last_response = {"type": "help", "commands": available_commands()}
                else:
                    last_response = controller.execute(command)
                message = ""
            except ClientCommandError as exc:
                message = f"error: {exc}"
            command = ""
        elif ch in (27,):  # ESC
            controller.running = False
        elif ch in (curses.KEY_BACKSPACE, 127, 8):
            command = command[:-1]
        elif 0 <= ch < 256:
            command += chr(ch)


if __name__ == "__main__":
    raise SystemExit(main())
