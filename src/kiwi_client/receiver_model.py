"""Minimal receiver/session state derived from KiwiSDR protocol messages."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ReceiverState:
    """State needed to contextualize early SND audio frames."""

    sample_rate: float | None = None
    audio_rate: int | None = None
    version_major: int | None = None
    version_minor: int | None = None
    bandwidth_hz: int | None = None

    @property
    def kiwi_version(self) -> float | None:
        """Return Kiwi version as major.minor-style float when known."""
        if self.version_major is None or self.version_minor is None:
            return None
        return self.version_major + self.version_minor / 1000.0

    def apply_msg_params(self, params: dict[str, str | None]) -> "ReceiverState":
        """Return updated state after applying one MSG parameter dictionary."""
        values = {
            "sample_rate": self.sample_rate,
            "audio_rate": self.audio_rate,
            "version_major": self.version_major,
            "version_minor": self.version_minor,
            "bandwidth_hz": self.bandwidth_hz,
        }

        if params.get("sample_rate") is not None:
            values["sample_rate"] = float(params["sample_rate"])
        if params.get("audio_rate") is not None:
            values["audio_rate"] = int(params["audio_rate"])
        if params.get("version_maj") is not None:
            values["version_major"] = int(params["version_maj"])
        if params.get("version_min") is not None:
            values["version_minor"] = int(params["version_min"])
        if params.get("bandwidth") is not None:
            values["bandwidth_hz"] = int(params["bandwidth"])

        return ReceiverState(**values)
