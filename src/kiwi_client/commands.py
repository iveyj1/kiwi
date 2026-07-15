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


def encode_ar_ok(input_rate: int, output_rate: int = 44100) -> str:
    """Acknowledge KiwiSDR audio rate setup."""
    return f"SET AR OK in={input_rate:d} out={output_rate:d}"


def encode_squelch(enabled: bool = False, threshold: int = 0) -> str:
    """Encode basic squelch state."""
    return f"SET squelch={int(enabled)} max={threshold:d}"


def encode_gen(frequency: int = 0, attenuation: int = 0, mix: int = -1) -> list[str]:
    """Encode signal generator/attenuator setup commands."""
    return [f"SET genattn={attenuation:d}", f"SET gen={frequency:d} mix={mix:d}"]


def encode_modulation(mod: str, low_cut: int, high_cut: int, freq_khz: float, *, frequency_decimals: int = 3) -> str:
    """Encode the basic frequency/mode/passband command."""
    decimals = max(0, int(frequency_decimals))
    return f"SET mod={mod.lower()} low_cut={low_cut:d} high_cut={high_cut:d} freq={freq_khz:.{decimals}f}"


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
    frequency_decimals: int = 3,
) -> list[str]:
    """Build the first fixture-tested non-admin SND setup command sequence."""
    return [
        encode_squelch(False, 0),
        *encode_gen(0, 0),
        encode_ident_user(user),
        encode_modulation(modulation, low_cut, high_cut, frequency_khz, frequency_decimals=frequency_decimals),
        encode_agc(agc),
        encode_compression(compression),
        encode_keepalive(),
    ]
