import pytest

from kiwi_client.session_manager import (
    DirectFrequency,
    RecenterWaterfall,
    RadioSessionManager,
    RadioSessionSnapshot,
    SelectFrequency,
    SetSessionIntent,
    TransportUpdate,
    TuneSelected,
    ToggleAudio,
    ZoomWaterfall,
)


def manager(**overrides):
    values = dict(
        desired_receiver="10.0.0.40:8073",
        frequency_khz=5000.0,
        selected_khz=5000.0,
        mode="am",
        low_cut_hz=-5000,
        high_cut_hz=5000,
        cw_offset_hz=-800,
        frequency_decimals=4,
        waterfall_center_khz=5000.0,
        waterfall_zoom=7,
        waterfall_zoom_max=14,
    )
    values.update(overrides)
    return RadioSessionManager(RadioSessionSnapshot(**values))


def test_direct_frequency_updates_shared_state_and_routes_snd_and_wf_commands():
    session = manager()

    result = session.dispatch(DirectFrequency(335.1255))

    assert result.state.frequency_khz == pytest.approx(335.1255)
    assert result.state.selected_khz == pytest.approx(335.1255)
    assert result.state.waterfall_center_khz == pytest.approx(335.1255)
    assert result.commands.snd == (
        "SET mod=am low_cut=-5000 high_cut=5000 freq=335.1255",
    )
    assert result.commands.waterfall == ("SET zoom=7 cf=335.1255",)


def test_cw_tune_applies_offset_but_keeps_user_frequency():
    session = manager(mode="cw", low_cut_hz=650, high_cut_hz=1050)
    session.dispatch(SelectFrequency(335.1255))

    result = session.dispatch(TuneSelected())

    assert result.state.frequency_khz == pytest.approx(335.1255)
    assert result.commands.snd == (
        "SET mod=cw low_cut=650 high_cut=1050 freq=334.3255",
    )
    assert result.commands.waterfall == ()


def test_recenter_and_zoom_use_selected_frequency_and_bounds():
    session = manager(selected_khz=5001.25, waterfall_zoom=13, waterfall_zoom_max=14)

    recentered = session.dispatch(RecenterWaterfall())
    zoomed = session.dispatch(ZoomWaterfall(1))
    bounded = session.dispatch(ZoomWaterfall(1))

    assert recentered.commands.waterfall == ("SET zoom=13 cf=5001.2500",)
    assert zoomed.state.waterfall_zoom == 14
    assert zoomed.commands.waterfall == ("SET zoom=14 cf=5001.2500",)
    assert bounded.commands.waterfall == ()


def test_audio_toggle_is_typed_local_state_without_receiver_command():
    session = manager(audio_enabled=False)

    result = session.dispatch(ToggleAudio())

    assert result.state.audio_enabled is True
    assert result.commands.snd == result.commands.waterfall == ()


def test_session_generation_ignores_stale_transport_updates_and_errors():
    session = manager()

    starting = session.dispatch(SetSessionIntent(running=True, receiver="10.0.0.41:8073"))
    generation = starting.state.generation
    session.dispatch(TransportUpdate("snd", "ready", generation=generation, active_receiver="10.0.0.41:8073"))
    session.dispatch(TransportUpdate("wf", "ready", generation=generation))
    stale = session.dispatch(TransportUpdate("snd", "failed", generation=generation - 1, error="old busy"))

    assert stale.state.snd_status == "ready"
    assert stale.state.wf_status == "ready"
    assert stale.state.active_receiver == "10.0.0.41:8073"
    assert stale.state.error is None

    failed = session.dispatch(TransportUpdate("wf", "failed", generation=generation, error="W/F closed"))
    assert failed.state.error is not None
    assert failed.state.error.stream == "wf"
    assert failed.state.error.generation == generation


def test_new_session_generation_clears_old_active_receiver_and_error():
    session = manager()
    first = session.dispatch(SetSessionIntent(running=True)).state.generation
    session.dispatch(TransportUpdate("snd", "failed", generation=first, error="busy"))

    restarted = session.dispatch(SetSessionIntent(running=True, receiver="10.0.0.41:8073"))

    assert restarted.state.generation == first + 1
    assert restarted.state.active_receiver is None
    assert restarted.state.error is None
    assert restarted.state.snd_status == "starting"
    assert restarted.state.wf_status == "waiting"
