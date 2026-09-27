"""Integrated-console zoom/passband/step checkpoints in the startup state file."""
from dataclasses import replace
import math

from kiwi_client.client_app import ClientController, ClientState
from kiwi_client.config import KiwiClientConfig, resolve_state_path
from kiwi_client.state_store import load_state_file, save_state_file


def startup_waterfall_zoom(config: KiwiClientConfig) -> int:
    if config.startup.mode.lower() != 'last':
        return config.waterfall.zoom
    last = load_state_file(resolve_state_path(config)).get('last_state') or {}
    return last.get('waterfall_zoom', config.waterfall.zoom)


def normalize_console_cw_bandwidth(state: ClientState) -> ClientState:
    """Migrate old sub-10 Hz CW settings without changing actual RF passband center."""
    bands = dict(state.mode_passbands)
    if 'cw' in bands:
        low, high = bands['cw']
        if 0 < high - low < 10:
            midpoint = math.floor((low + high) / 2)
            bands['cw'] = (midpoint - 5, midpoint + 5)
    changes = dict(mode_passbands=bands)
    if state.mode == 'cw' and 0 < state.high_cut_hz - state.low_cut_hz < 10:
        old_midpoint = (state.low_cut_hz + state.high_cut_hz) / 2
        midpoint = math.floor(old_midpoint)
        changes.update(low_cut_hz=midpoint - 5, high_cut_hz=midpoint + 5,
                       frequency_khz=state.frequency_khz + (old_midpoint - midpoint) / 1000)
        bands['cw'] = (midpoint - 5, midpoint + 5)
    return replace(state, **changes)


def startup_waterfall_scale(config: KiwiClientConfig) -> dict:
    defaults = dict(min_dbm=-100, max_dbm=-40, automatic=False)
    if config.startup.mode.lower() != 'last':
        return defaults
    last = load_state_file(resolve_state_path(config)).get('last_state') or {}
    return last.get('waterfall_scale', defaults)


class ConsoleSettingsCheckpoint:
    def __init__(self, config: KiwiClientConfig) -> None:
        self.path = resolve_state_path(config)
        self.last_attempt = None

    def save_if_changed(self, controller: ClientController, *, levels=None, force: bool = False) -> bool:
        state = controller.state
        zoom = controller.paired_session.state.waterfall_zoom
        key = (state.receiver, state.mode, state.low_cut_hz, state.high_cut_hz,
               tuple(sorted((mode, tuple(cuts)) for mode, cuts in state.mode_passbands.items())),
               tuple(sorted(state.mode_step_indices.items())), zoom)
        scale = None
        if levels is not None:
            scale = dict(min_dbm=levels.min_dbm, max_dbm=levels.max_dbm, automatic=levels.automatic)
            # Automatic adaptation is telemetry, not a user settings change.
            key += ((True,) if levels.automatic else (False, levels.min_dbm, levels.max_dbm),)
        if not force and key == self.last_attempt:
            return False
        # Do not retry a failing filesystem every frame; retry on change or orderly exit.
        self.last_attempt = key
        save_state_file(self.path, last_state=state, waterfall_zoom=zoom, waterfall_scale=scale)
        return True
