"""System output volume helpers for the local client."""

from __future__ import annotations

import re
import shutil
import subprocess
from dataclasses import dataclass
from typing import Protocol


class VolumeControl(Protocol):
    """Interface for setting local system output volume."""

    def get_percent(self) -> int: ...

    def set_percent(self, percent: int) -> dict: ...


@dataclass(frozen=True)
class SystemVolumeControl:
    """Set local system output volume using common Linux mixer tools.

    Backend preference is PipeWire/WirePlumber `wpctl`, then PulseAudio
    `pactl`, then ALSA `amixer`.
    """

    def get_percent(self) -> int:
        command = self._get_command()
        if command is None:
            raise RuntimeError("no supported system volume command found: tried wpctl, pactl, amixer")
        try:
            result = subprocess.run(command, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        except subprocess.CalledProcessError as exc:
            detail = exc.stderr.strip() if exc.stderr else repr(exc)
            raise RuntimeError(f"system volume command failed: {detail}") from exc
        return self._parse_percent(result.stdout)

    def set_percent(self, percent: int) -> dict:
        percent = max(0, min(200, int(percent)))
        command = self._command(percent)
        if command is None:
            raise RuntimeError("no supported system volume command found: tried wpctl, pactl, amixer")
        try:
            subprocess.run(command, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True)
        except subprocess.CalledProcessError as exc:
            detail = exc.stderr.strip() if exc.stderr else repr(exc)
            raise RuntimeError(f"system volume command failed: {detail}") from exc
        return {"backend": command[0], "percent": percent}

    @staticmethod
    @staticmethod
    def _get_command() -> list[str] | None:
        if shutil.which("wpctl"):
            return ["wpctl", "get-volume", "@DEFAULT_AUDIO_SINK@"]
        if shutil.which("pactl"):
            return ["pactl", "get-sink-volume", "@DEFAULT_SINK@"]
        if shutil.which("amixer"):
            return ["amixer", "get", "Master"]
        return None

    @staticmethod
    def _parse_percent(output: str) -> int:
        wpctl = re.search(r"Volume:\s*([0-9]+(?:\.[0-9]+)?)", output)
        if wpctl:
            return max(0, min(200, int(round(float(wpctl.group(1)) * 100))))
        match = re.search(r"(\d+)%", output)
        if match:
            return max(0, min(200, int(match.group(1))))
        raise RuntimeError(f"could not parse system volume output: {output!r}")

    @staticmethod
    def _command(percent: int) -> list[str] | None:
        if shutil.which("wpctl"):
            return ["wpctl", "set-volume", "@DEFAULT_AUDIO_SINK@", f"{percent}%"]
        if shutil.which("pactl"):
            return ["pactl", "set-sink-volume", "@DEFAULT_SINK@", f"{percent}%"]
        if shutil.which("amixer"):
            return ["amixer", "sset", "Master", f"{percent}%"]
        return None
