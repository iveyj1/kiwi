"""KiwiSDR command encoding helpers.

These helpers only build command strings. Transport code is responsible for
sending them over a WebSocket.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class AgcSettings:
    """KiwiSDR AGC command settings matching kiwiclient defaults."""

    on: bool = True
    hang: bool = False
    thresh: int = -100
    slope: int = 6
    decay: int = 1000
    gain: int = 50


def encode_auth(client_type: str = "kiwi", password: str = "", tlimit_password: str = "") -> str:
    """Encode a KiwiSDR auth command."""
    if tlimit_password:
        if not password:
            password = "#"
        return f"SET auth t={client_type} p={password} ipl={tlimit_password}"
    return f"SET auth t={client_type} p={password}"


def encode_ident_user(name: str) -> str:
    """Encode the user identity command."""
    return f"SET ident_user={name}"


def encode_keepalive() -> str:
    """Encode a keepalive command."""
    return "SET keepalive"


def encode_modulation(mod: str, low_cut: int, high_cut: int, freq_khz: float) -> str:
    """Encode the basic frequency/mode/passband command."""
    return f"SET mod={mod.lower()} low_cut={low_cut:d} high_cut={high_cut:d} freq={freq_khz:.3f}"


def encode_agc(settings: AgcSettings | None = None) -> str:
    """Encode an AGC command."""
    if settings is None:
        settings = AgcSettings()
    return (
        f"SET agc={int(settings.on)} hang={int(settings.hang)} "
        f"thresh={settings.thresh:d} slope={settings.slope:d} "
        f"decay={settings.decay:d} manGain={settings.gain:d}"
    )


def encode_compression(enabled: bool) -> str:
    """Encode the SND audio compression command."""
    return f"SET compression={int(enabled)}"


def encode_basic_snd_setup(
    *,
    user: str,
    frequency_khz: float,
    modulation: str = "am",
    low_cut: int = -4900,
    high_cut: int = 4900,
    compression: bool = False,
    agc: AgcSettings | None = None,
) -> list[str]:
    """Build the first fixture-tested non-admin SND setup command sequence."""
    return [
        encode_ident_user(user),
        encode_modulation(modulation, low_cut, high_cut, frequency_khz),
        encode_agc(agc),
        encode_compression(compression),
        encode_keepalive(),
    ]
