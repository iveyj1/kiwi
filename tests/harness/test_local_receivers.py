"""Offline consistency checks for the current local receiver deployment."""

import importlib
import tomllib
from pathlib import Path

import pytest

from kiwi_client.client_app import ClientState
from kiwi_client.config import ReceiverConfig, default_config
from kiwi_client.live_capture import LOCAL_RECEIVERS, LiveCaptureError
from kiwi_client.live_play import LiveSndPlaybackConfig


HOSTS = ("10.0.0.41", "10.0.0.42", "10.0.0.43")
RECEIVERS = tuple(f"{host}:8073" for host in HOSTS)


def test_local_receiver_defaults_agree():
    assert LOCAL_RECEIVERS == {(host, 8073) for host in HOSTS}
    assert ReceiverConfig().allowed == RECEIVERS
    assert default_config().receivers.allowed == RECEIVERS
    assert ClientState().allowed_receivers == RECEIVERS
    assert ClientState().host == LiveSndPlaybackConfig().host == HOSTS[0]


@pytest.mark.parametrize("host", HOSTS)
def test_guard_accepts_all_current_local_receivers(host):
    LiveSndPlaybackConfig(host=host).validate()


def test_guard_rejects_retired_receiver():
    with pytest.raises(LiveCaptureError, match="allowed receivers"):
        LiveSndPlaybackConfig(host="10.0.0.40").validate()


@pytest.mark.parametrize("module", [
    "live_capture", "live_play", "live_record", "live_waterfall",
    "live_waterfall_preview", "waterfall_terminal",
])
def test_cli_host_defaults(module):
    parser = importlib.import_module(f"kiwi_client.{module}").build_arg_parser()
    assert parser.get_default("host") == HOSTS[0]


def test_checked_in_local_registers_and_configuration():
    presets = tomllib.loads(Path("presets.toml").read_text())
    config = tomllib.loads(Path("config.toml").read_text())
    assert tuple(presets["receiver_presets"][str(i)]["receiver"] for i in (1, 2, 3)) == RECEIVERS
    assert set(RECEIVERS) <= set(config["receivers"]["allowed"])
    assert config["default_state"]["host"] == HOSTS[0]
    assert all(preset.get("host") != "10.0.0.40" for preset in presets["radio_presets"].values())
