from kiwi_client.waterfall import WaterfallFrame
from kiwi_client.waterfall_levels import WaterfallLevelController
from kiwi_client.waterfall_snapshots import WaterfallSnapshotPublisher


def snapshot_with_rows(rows):
    publisher = WaterfallSnapshotPublisher(max_rows=len(rows))
    snapshot = None
    for sequence, values in enumerate(rows):
        snapshot = publisher.append(WaterfallFrame(sequence=sequence, bins=(0,) * len(values), dbm=tuple(values)))
    return snapshot


def test_manual_level_adjustments_are_independent_and_disable_auto():
    levels = WaterfallLevelController(min_dbm=-100, max_dbm=-40, automatic=True)

    levels.adjust_min(5)
    assert levels.min_dbm == -95
    assert levels.max_dbm == -40
    assert levels.automatic is False

    levels.set_automatic(True)
    levels.adjust_max(-5)
    assert levels.min_dbm == -95
    assert levels.max_dbm == -45
    assert levels.automatic is False


def test_auto_levels_use_percentiles_padding_and_bounded_smoothing():
    snapshot = snapshot_with_rows([
        [-120, -100, -99, -98, -97, -96, -95, -40],
        [-120, -101, -100, -99, -98, -97, -60, -20],
    ])
    levels = WaterfallLevelController(
        min_dbm=-110,
        max_dbm=-30,
        automatic=True,
        smoothing=0.5,
        update_generations=1,
        low_percentile=0.10,
        high_percentile=0.90,
        padding_db=3,
    )

    changed = levels.observe(snapshot)

    assert changed is True
    assert -117 < levels.min_dbm < -105
    assert -45 < levels.max_dbm < -30
    assert levels.max_dbm - levels.min_dbm >= levels.minimum_range_db


def test_auto_levels_skip_intermediate_generations_and_manual_mode():
    snapshot = snapshot_with_rows([[-100, -90], [-80, -70]])
    levels = WaterfallLevelController(automatic=True, update_generations=10)

    assert levels.observe(snapshot) is False
    levels.set_automatic(False)
    assert levels.observe(snapshot) is False


def test_level_status_reports_mode_and_range():
    levels = WaterfallLevelController(min_dbm=-105, max_dbm=-35, automatic=False)
    assert levels.status_text() == "scale manual -105..-35 dB"
    levels.set_automatic(True)
    assert levels.status_text() == "scale auto -105..-35 dB"
