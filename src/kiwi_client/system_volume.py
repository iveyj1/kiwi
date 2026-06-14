"""System output volume helpers for the local client."""

from __future__ import annotations

import shutil
import subprocess
from dataclasses import dataclass
from typing import Protocol


class VolumeControl(Protocol):
    """Interface for setting local system output volume."""

    def set_percent(self, percent: int) -> dict: ...


@dataclass(frozen=True)
class SystemVolumeControl:
    """Set local system output volume using common Linux mixer tools.

    Backend preference is PipeWire/WirePlumber `wpctl`, then PulseAudio
    `pactl`, then ALSA `amixer`.
    """

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
    def _command(percent: int) -> list[str] | None:
        if shutil.which("wpctl"):
            return ["wpctl", "set-volume", "@DEFAULT_AUDIO_SINK@", f"{percent}%"]
        if shutil.which("pactl"):
            return ["pactl", "set-sink-volume", "@DEFAULT_SINK@", f"{percent}%"]
        if shutil.which("amixer"):
            return ["amixer", "sset", "Master", f"{percent}%"]
        return None
