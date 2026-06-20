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

from kiwi_client.client_app import (
    REGISTER_KEYS,
    ClientCommandError,
    ClientController,
    ClientState,
    available_commands,
    normalize_receiver_address,
    command_aliases,
)
from kiwi_client.config import (
    KiwiClientConfig,
    add_allowed_receiver_to_config,
    discover_config_path,
    load_config,
    resolve_presets_path,
    resolve_state_path,
)
from kiwi_client.state_store import apply_preset, load_presets_file, load_state_file, save_presets_file, save_state_file


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
    pending_key_action: str | None = None


@dataclass(frozen=True)
class DashboardModel:
    """Data needed to render the basic client dashboard."""

    state: ClientState
    last_response: dict[str, Any] | None = None
    message: str = ""


@dataclass(frozen=True)
class CommandHint:
    """Short command help used by command-mode hints."""

    name: str
    description: str
    usage: str
    category: str
    detail: str = ""


COMMAND_HINTS = [
    CommandHint("status", "show state", "status", "Status"),
    CommandHint("dashboard", "show dashboard", "dashboard", "Status"),
    CommandHint("operation-status", "worker status", "operation-status", "Status"),
    CommandHint("connect", "mark connected", "connect", "Connection"),
    CommandHint("disconnect", "mark disconnected", "disconnect", "Connection"),
    CommandHint("receiver", "set receiver", "receiver <host>[:port]", "Connection"),
    CommandHint("add-receiver", "save receiver", "add-receiver <receiver-register> <ip/url[:port]> <description>", "Connection"),
    CommandHint("tune", "set frequency", "tune <frequency_khz>", "Tuning"),
    CommandHint("mode", "set demod mode", "mode <mode> [low_cut_hz high_cut_hz]", "Tuning"),
    CommandHint("filter", "set passband", "filter <low_cut_hz> <high_cut_hz>", "Tuning"),
    CommandHint("tune-step", "step frequency", "tune-step <+/-hz|small|medium|large>", "Tuning"),
    CommandHint("volume", "set local volume", "volume <percent>", "Audio controls"),
    CommandHint("volume-step", "step local volume", "volume-step <delta_percent>", "Audio controls"),
    CommandHint(
        "agc",
        "AGC settings",
        "agc [sub-option]",
        "Audio controls",
        "sub-options: on, off, hang on|off, threshold <value>, slope <value>, decay <ms>, gain <value>, set key=value ...",
    ),
    CommandHint("store", "save preset", "store <n> | store all <n>", "Presets"),
    CommandHint("recall", "load preset", "recall <n>", "Presets"),
    CommandHint("duration", "set live limit", "duration <seconds>", "Live limits"),
    CommandHint("frames", "set frame limit", "frames <max_snd_frames>", "Live limits"),
    CommandHint("play-plan", "show play plan", "play-plan", "Playback"),
    CommandHint("play", "play now", "play --allow-live [--null-sink]", "Playback"),
    CommandHint("play-bg", "start playback worker", "play-bg --allow-live [--null-sink]", "Playback"),
    CommandHint("record-plan", "show record plan", "record-plan <output.wav>", "Recording/capture"),
    CommandHint("record", "record now", "record <output.wav> --allow-live [--overwrite]", "Recording/capture"),
    CommandHint("record-bg", "start record worker", "record-bg <output.wav> --allow-live [--overwrite]", "Recording/capture"),
    CommandHint("capture-plan", "show capture plan", "capture-plan <output.jsonl>", "Recording/capture"),
    CommandHint("capture", "capture now", "capture <output.jsonl> --allow-live [--overwrite]", "Recording/capture"),
    CommandHint("capture-bg", "start capture worker", "capture-bg <output.jsonl> --allow-live [--overwrite]", "Recording/capture"),
    CommandHint("stop", "stop worker", "stop", "Worker"),
    CommandHint("wait", "wait for worker", "wait [seconds]", "Worker"),
    CommandHint("help", "list commands", "help", "Other"),
    CommandHint("quit", "quit TUI", "quit", "Other"),
]


def render_tui_hints(
    input_state: TuiInputState,
    config: KiwiClientConfig,
    controller: ClientController | None = None,
) -> str:
    """Render context-sensitive key/command hints for the current input mode."""
    if input_state.mode == InputMode.COMMAND:
        return render_command_hints(input_state.command)
    if input_state.pending_key_action is not None:
        return render_pending_keymap_hints(input_state.pending_key_action, config, controller)
    return render_keymap_hints(config)


def render_pending_keymap_hints(
    pending_key_action: str,
    config: KiwiClientConfig,
    controller: ClientController | None = None,
) -> str:
    """Render hints after a keymap prefix has been pressed."""
    labels = {
        "recall-preset": "Recall preset",
        "store-preset": "Store preset (frequency, mode and bandwidth only)",
        "store-all-preset": "Store preset (all radio parameters)",
        "receiver": "Receiver",
    }
    lines = ["Key hints", labels.get(pending_key_action, pending_key_action)]
    if pending_key_action == "receiver":
        receiver_lines: dict[str, str] = {}
        for index, receiver in enumerate(config.receivers.allowed[: len(REGISTER_KEYS)]):
            register = REGISTER_KEYS[index]
            receiver_lines[register] = f"{register} — {receiver}"
        if controller is not None:
            for register, preset in sorted_receiver_registers(controller.receiver_presets):
                host, port = normalize_receiver_address(preset["receiver"], default_port=8073)
                receiver_lines[register] = f"{register} — {host}:{port} {preset['description']}"
        for register in REGISTER_KEYS:
            if register in receiver_lines:
                lines.append(receiver_lines[register])
        lines.append("Radio parameters are transferred to new receiver")
    else:
        lines.append("<register> is [0..9] or [a..z]")
        if controller is not None:
            for register, preset in sorted_preset_registers(controller.presets):
                frequency = preset.get("frequency_khz")
                mode = preset.get("mode")
                if frequency is not None and mode is not None:
                    lines.append(f"{register} — {float(frequency):.3f} kHz {mode}")
    return "\n".join(lines)


def sorted_receiver_registers(receiver_presets: dict[Any, dict[str, str]]) -> list[tuple[str, dict[str, str]]]:
    """Return receiver registers sorted in keymap register order."""
    def register_index(item: tuple[Any, dict[str, str]]) -> int:
        key = str(item[0]).lower()
        return REGISTER_KEYS.index(key) if len(key) == 1 and key in REGISTER_KEYS else len(REGISTER_KEYS)

    return [(str(key), value) for key, value in sorted(receiver_presets.items(), key=register_index)]


def sorted_preset_registers(presets: dict[Any, dict[str, Any]]) -> list[tuple[str, dict[str, Any]]]:
    """Return preset registers sorted in keymap register order."""
    def register_index(item: tuple[Any, dict[str, Any]]) -> int:
        key = str(item[0]).lower()
        return REGISTER_KEYS.index(key) if len(key) == 1 and key in REGISTER_KEYS else len(REGISTER_KEYS)

    return [(str(key), value) for key, value in sorted(presets.items(), key=register_index)]


def render_keymap_hints(config: KiwiClientConfig) -> str:
    """Render requested which-key style hints for keymap mode."""
    rows = [
        ("Tuning", ["h — tune down", "l — tune up"]),
        ("Tuning modifiers", ["<shift> h/l — small step", "<ctrl> h/l — large step"]),
        ("Volume", ["k — volume up", "j — volume down"]),
        (
            "Presets",
            [
                "p <register> — recall preset",
                "s <register> — store preset (frequency, mode and bandwidth only)",
                "S <register> — store preset (all radio parameters)",
                "<register> is [0..9] or [a..z]",
                "r <receiver> — switch to specified receiver",
                "<receiver> is [0..9] or [a..z] from list of receivers",
                "Radio parameters are transferred to new receiver",
            ],
        ),
        ("Other", [": — command mode", "q — quit"]),
    ]
    return "\n".join(["Key hints", *format_hint_categories_two_columns(rows)])


def render_command_hints(command_text: str) -> str:
    """Render command-mode hints filtered by the active semicolon segment."""
    segment = active_command_segment(command_text)
    token = segment.split(maxsplit=1)[0].lower() if segment.split(maxsplit=1) else ""
    matches = matching_command_hints(token)
    lines = ["Command hints"]
    if segment:
        lines.append(f"active: {segment}")
    if not matches:
        lines.append("no matching commands")
        return "\n".join(lines)
    unique = unique_command_hint(token, matches)
    if unique is not None:
        lines.append(format_command_hint(unique))
        lines.append(f"args: {unique.usage}")
        if unique.detail:
            lines.append(unique.detail)
        return "\n".join(lines)
    rows = [(category, [format_command_hint(hint) for hint in category_hints]) for category, category_hints in grouped_command_hints(matches)]
    lines.extend(format_hint_categories_two_columns(rows))
    return "\n".join(lines)


def format_hint_categories_two_columns(categories: list[tuple[str, list[str]]], *, column_width: int = 52) -> list[str]:
    """Format categorized hints into two compact text columns."""
    blocks: list[list[str]] = []
    for category, items in categories:
        block = [category, *[f"    {item}" for item in items]]
        blocks.append(block)
    left_blocks = blocks[0::2]
    right_blocks = blocks[1::2]
    lines: list[str] = []
    for index in range(max(len(left_blocks), len(right_blocks))):
        left = left_blocks[index] if index < len(left_blocks) else []
        right = right_blocks[index] if index < len(right_blocks) else []
        height = max(len(left), len(right))
        for row in range(height):
            left_text = left[row] if row < len(left) else ""
            right_text = right[row] if row < len(right) else ""
            if right_text:
                lines.append(f"{left_text:<{column_width}}{right_text}")
            else:
                lines.append(left_text.rstrip())
    return lines


def active_command_segment(command_text: str) -> str:
    """Return text after the last unquoted semicolon."""
    quote: str | None = None
    escaped = False
    start = 0
    for index, char in enumerate(command_text):
        if escaped:
            escaped = False
            continue
        if char == "\\" and quote != "'":
            escaped = True
            continue
        if char in {"'", '"'}:
            if quote is None:
                quote = char
            elif quote == char:
                quote = None
            continue
        if char == ";" and quote is None:
            start = index + 1
    return command_text[start:].strip()


def grouped_command_hints(hints: list[CommandHint]) -> list[tuple[str, list[CommandHint]]]:
    """Return command hints grouped by category while preserving command order."""
    groups: list[tuple[str, list[CommandHint]]] = []
    by_category: dict[str, list[CommandHint]] = {}
    for hint in hints:
        if hint.category not in by_category:
            by_category[hint.category] = []
            groups.append((hint.category, by_category[hint.category]))
        by_category[hint.category].append(hint)
    return groups


def matching_command_hints(token: str) -> list[CommandHint]:
    """Return command hints matching a full-name or alias prefix."""
    aliases = command_aliases()
    reverse_aliases = aliases_by_command()
    if not token:
        return list(COMMAND_HINTS)
    matches: list[CommandHint] = []
    for hint in COMMAND_HINTS:
        if hint.name.startswith(token) or any(alias.startswith(token) for alias in reverse_aliases.get(hint.name, [])):
            matches.append(hint)
    return matches


def unique_command_hint(token: str, matches: list[CommandHint]) -> CommandHint | None:
    """Return a uniquely specified command hint, if any."""
    if not token:
        return None
    aliases = aliases_by_command()
    exact = [hint for hint in matches if hint.name == token or token in aliases.get(hint.name, [])]
    if len(exact) == 1:
        return exact[0]
    return matches[0] if len(matches) == 1 else None


def aliases_by_command() -> dict[str, list[str]]:
    """Return aliases grouped by canonical command."""
    grouped: dict[str, list[str]] = {}
    for alias, command in command_aliases().items():
        grouped.setdefault(command, []).append(alias)
    return grouped


def format_command_hint(hint: CommandHint) -> str:
    """Format one command hint line with shortcuts before full command names."""
    aliases = sorted(aliases_by_command().get(hint.name, []))
    if aliases:
        return f"{', '.join(aliases)} ({hint.name}) — {hint.description}"
    return f"{hint.name} — {hint.description}"


def describe_key_action(action: str) -> str:
    """Return a short description for a configured key action."""
    if action == "command-mode":
        return "command mode"
    if action == "quit":
        return "quit"
    if action.startswith("tune-step "):
        step = action.split(maxsplit=1)[1]
        direction = "down" if step.startswith("-") else "up"
        name = step.lstrip("+-")
        return f"tune {direction} {name}"
    if action.startswith("volume-step "):
        step = action.split(maxsplit=1)[1]
        direction = "down" if step.startswith("-") else "up"
        return f"volume {direction}"
    if action.startswith("store all"):
        return "store full preset"
    if action.startswith("store"):
        return "store preset"
    if action.startswith("recall"):
        return "recall preset"
    return action


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
        f"Connected: {'yes' if state.connected or (operation is not None and operation.get('running')) else 'no'}",
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
        if "active_commands" in last_response:
            for active_command in last_response["active_commands"]:
                lines.append(f"Applied to active stream: {active_command}")
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


def request_tui_quit(
    controller: ClientController,
    *,
    join_timeout: float = 2.0,
    config: KiwiClientConfig | None = None,
) -> tuple[dict[str, Any] | None, str]:
    """Safely quit the TUI, stopping any active background operation first."""
    status = controller.background.status()
    if status.running:
        controller.background.stop()
        final = controller.background.join(timeout=join_timeout)
        if final.running:
            return {"type": "operation-status", "operation": final.as_dict()}, "Stopping background operation before quit..."
        controller.running = False
        persist_tui_state(controller, config)
        return {"type": "operation-status", "operation": final.as_dict()}, "Stopped background operation and quitting."
    controller.running = False
    persist_tui_state(controller, config)
    return {"type": "quit"}, ""


def handle_pending_keymap_register(
    key_name: str | None,
    input_state: TuiInputState,
    controller: ClientController,
    config: KiwiClientConfig,
) -> tuple[dict[str, Any] | None, str | None]:
    """Handle the register following a keymap prefix command."""
    pending = input_state.pending_key_action
    input_state.pending_key_action = None
    if key_name is None or len(key_name) != 1 or key_name not in REGISTER_KEYS:
        return None, "error: expected register [0..9] or [a..z]"
    try:
        if pending == "recall-preset":
            return controller.execute(f"recall {key_name}"), ""
        if pending == "store-preset":
            return controller.execute(f"store {key_name}"), ""
        if pending == "store-all-preset":
            return controller.execute(f"store all {key_name}"), ""
        if pending == "receiver":
            receiver = receiver_for_register(key_name, config, controller)
            return switch_receiver_from_keymap(controller, receiver)
    except ClientCommandError as exc:
        return None, f"error: {exc}"
    return None, None


def switch_receiver_from_keymap(
    controller: ClientController,
    receiver: str,
    *,
    join_timeout: float = 2.0,
    startup_grace_seconds: float = 0.1,
) -> tuple[dict[str, Any] | None, str | None]:
    """Switch receiver from keymap mode, delegating lifecycle policy to the controller."""
    return controller.switch_receiver(
        receiver,
        preserve_playback=True,
        join_timeout=join_timeout,
        startup_grace_seconds=startup_grace_seconds,
    )


def play_bg_command(null_sink: bool) -> str:
    """Return a guarded play-bg command matching previous sink choice."""
    command = "play-bg --allow-live"
    if null_sink:
        command += " --null-sink"
    return command


def receiver_for_register(register: str, config: KiwiClientConfig, controller: ClientController | None = None) -> str:
    """Return a stored or configured receiver address for a register key."""
    parsed_register = int(register) if register.isdigit() else register
    if controller is not None and parsed_register in controller.receiver_presets:
        host, port = normalize_receiver_address(controller.receiver_presets[parsed_register]["receiver"], default_port=8073)
        return f"{host}:{port}"
    if controller is not None and register in controller.receiver_presets:
        host, port = normalize_receiver_address(controller.receiver_presets[register]["receiver"], default_port=8073)
        return f"{host}:{port}"
    index = REGISTER_KEYS.index(register)
    if index >= len(config.receivers.allowed):
        raise ClientCommandError(f"unknown receiver register: {register}")
    return config.receivers.allowed[index]


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
        if input_state.pending_key_action is not None:
            return handle_pending_keymap_register(key_name, input_state, controller, config)
        if key_name == "p":
            input_state.pending_key_action = "recall-preset"
            return None, "Recall preset: press register [0..9] or [a..z]"
        if key_name == "s":
            input_state.pending_key_action = "store-preset"
            return None, "Store preset: press register [0..9] or [a..z]"
        if key_name == "shift-s":
            input_state.pending_key_action = "store-all-preset"
            return None, "Store all preset: press register [0..9] or [a..z]"
        if key_name == "r":
            input_state.pending_key_action = "receiver"
            return None, "Receiver: press register [0..9] or [a..z]"
        action = config.keys.get(key_name) if key_name is not None else None
        if action == "command-mode" or ch == ord(":"):
            input_state.mode = InputMode.COMMAND
            input_state.command = ""
            input_state.history_index = None
            return None, ""
        if action:
            if action == "quit":
                return request_tui_quit(controller, config=config)
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
            return request_tui_quit(controller, config=config)
        try:
            response = controller.execute(command)
            message = persist_added_receivers_to_config(response, config)
            return response, message
        except ClientCommandError as exc:
            return None, f"error: {exc}"
    if 0 <= ch < 256:
        input_state.command += chr(ch)
        input_state.history_index = None
    return None, None


def runtime_state_from_config(config: KiwiClientConfig, state: ClientState) -> ClientState:
    """Apply non-radio runtime settings from config to a state."""
    return replace(
        state,
        duration_seconds=config.live.duration_seconds,
        max_frames=config.live.max_frames,
        audio_startup_mute_ms=config.audio.startup_mute_ms,
        audio_startup_fade_in_ms=config.audio.startup_fade_in_ms,
        audio_stop_fade_out_ms=config.audio.stop_fade_out_ms,
        receivers_restricted=config.receivers.restricted,
        allowed_receivers=config.receivers.allowed,
    )


def state_from_config(config: KiwiClientConfig, state: ClientState | None = None) -> ClientState:
    """Return client state with default radio state plus runtime config."""
    state = state or ClientState()
    if config.default_state:
        state = apply_preset(state, config.default_state)
    return runtime_state_from_config(config, state)


def persist_added_receivers_to_config(response: dict[str, Any] | None, config: KiwiClientConfig) -> str:
    """Persist added receiver addresses to the config allowlist when possible."""
    if response is None or config.source_path is None:
        return ""
    receivers = receiver_addresses_from_response(response)
    changed: list[str] = []
    for receiver in receivers:
        if add_allowed_receiver_to_config(config.source_path, receiver):
            changed.append(receiver)
    if not changed:
        return ""
    return f"Saved receiver(s) to config: {', '.join(changed)}"


def receiver_addresses_from_response(response: dict[str, Any]) -> list[str]:
    """Return receiver addresses from command responses, including batches."""
    if response.get("type") == "receiver-preset" and isinstance(response.get("receiver"), str):
        return [response["receiver"]]
    addresses: list[str] = []
    for nested in response.get("responses", []) if isinstance(response.get("responses"), list) else []:
        if isinstance(nested, dict):
            addresses.extend(receiver_addresses_from_response(nested))
    return addresses


def startup_state_and_presets(config: KiwiClientConfig) -> tuple[ClientState, dict[int, dict[str, Any]]]:
    """Resolve startup state and presets from config/state file."""
    persisted = load_state_file(resolve_state_path(config))
    preset_data = load_presets_file(resolve_presets_path(config))
    presets = {int(key) if str(key).isdigit() else str(key): value for key, value in preset_data.get("presets", {}).items()}
    state = state_from_config(config)
    mode = config.startup.mode.lower()
    if mode == "last" and persisted.get("last_state"):
        state = runtime_state_from_config(config, apply_preset(state, persisted["last_state"]))
    elif mode == "preset" and config.startup.preset in presets:
        state = runtime_state_from_config(config, apply_preset(state, presets[config.startup.preset]))
    elif mode == "default":
        state = state_from_config(config)
    return state, presets


def startup_receiver_presets(config: KiwiClientConfig) -> dict[Any, dict[str, str]]:
    """Resolve stored receiver registers from the presets file."""
    preset_data = load_presets_file(resolve_presets_path(config))
    return {int(key) if str(key).isdigit() else str(key): value for key, value in preset_data.get("receiver_presets", {}).items()}


def persist_tui_state(controller: ClientController, config: KiwiClientConfig | None) -> None:
    """Persist last state and presets for future TUI startup."""
    if config is None:
        return
    save_state_file(resolve_state_path(config), last_state=controller.state)
    save_presets_file(resolve_presets_path(config), presets=controller.presets, receiver_presets=controller.receiver_presets)


def run_tui(controller: ClientController | None = None, *, config: KiwiClientConfig | None = None) -> None:
    """Run a small curses command UI."""
    config = config or load_config()
    startup_state, presets = startup_state_and_presets(config)
    receiver_presets = startup_receiver_presets(config)
    controller = controller or ClientController(
        state=startup_state,
        allow_live_default=config.live.allow_live,
        presets=presets,
        receiver_presets=receiver_presets,
    )
    if controller is not None:
        controller.allow_live_default = config.live.allow_live
        controller.state = runtime_state_from_config(config, controller.state)
        if not controller.presets:
            controller.presets.update(presets)
        if not controller.receiver_presets:
            controller.receiver_presets.update(receiver_presets)
    start_startup_playback(controller, config)
    curses.wrapper(_run_curses, controller, config)


def start_startup_playback(controller: ClientController, config: KiwiClientConfig) -> dict[str, Any] | None:
    """Start background playback at TUI startup when configured and allowed."""
    if not config.startup.playback or not config.live.allow_live:
        return None
    if controller.background.status().running:
        return None
    return controller.execute("play-bg --allow-live")


def build_arg_parser() -> argparse.ArgumentParser:
    """Build the TUI CLI argument parser."""
    parser = argparse.ArgumentParser(description="KiwiSDR curses TUI")
    parser.add_argument("--config", type=Path, help="optional TOML configuration file")
    return parser


def main(argv: list[str] | None = None) -> int:
    """CLI entrypoint for the curses TUI."""
    parser = build_arg_parser()
    args = parser.parse_args(argv)
    config = load_config(discover_config_path(args.config))
    startup_state, presets = startup_state_and_presets(config)
    receiver_presets = startup_receiver_presets(config)
    run_tui(
        ClientController(
            state=startup_state,
            allow_live_default=config.live.allow_live,
            presets=presets,
            receiver_presets=receiver_presets,
        ),
        config=config,
    )
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
        hints = render_tui_hints(input_state, config, controller)
        height, width = stdscr.getmaxyx()
        hint_lines = hints.splitlines()
        dashboard_limit = max(0, height - len(hint_lines) - 4)
        row = 0
        for line in dashboard.splitlines()[:dashboard_limit]:
            stdscr.addnstr(row, 0, line, max(0, width - 1))
            row += 1
        if row < height - 3:
            row += 1
        for line in hint_lines[: max(0, height - row - 2)]:
            stdscr.addnstr(row, 0, line, max(0, width - 1))
            row += 1
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
