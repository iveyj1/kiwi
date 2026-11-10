"""Small live-client fixes ported without importing recorded/analysis workflows."""
import json
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace

import pytest

from kiwi_client.gui_app import SnapshotRasterizer, WaterfallGuiModel, FixtureWaterfallTimeline
from kiwi_client.waterfall import WaterfallFrame
from kiwi_client.waterfall_levels import WaterfallLevelController
from kiwi_client.waterfall_snapshots import WaterfallSnapshotPublisher

DATA = json.loads(Path('tests/fixtures/terminal/merge-review-fixes.json').read_text())


def snapshot():
    publisher = WaterfallSnapshotPublisher(max_rows=DATA['history_rows'])
    frame = WaterfallFrame(sequence=0, bins=(0,) * DATA['width'], dbm=(-110,) * DATA['width'])
    return publisher, frame, publisher.append(frame)


def test_raster_padding_storage_is_bounded_as_history_fills():
    publisher, frame, first = snapshot()
    raster = SnapshotRasterizer(min_dbm=-120, max_dbm=-40)
    for _ in range(DATA['history_rows']):
        current = publisher.append(frame)
        image = raster.update(current)
        assert len(raster._padding_rows) <= 1
        assert sum(map(len, raster._padding_rows.values())) <= image.width * image.height * 3
        assert len(image.rgb) == image.width * image.height * 3


def test_raster_geometry_rebuild_discards_old_width_padding():
    _, _, first = snapshot()
    raster = SnapshotRasterizer(min_dbm=-120, max_dbm=-40)
    raster.update(first)
    new_width = DATA['width'] * 2
    second = replace(first, generation=first.generation + 1, width=new_width,
                     rows=(replace(first.rows[0], dbm=(-110,) * new_width),))
    image = raster.update(second)
    assert len(image.rgb) == new_width * DATA['history_rows'] * 3
    assert image.rgb[:new_width * (DATA['history_rows'] - 1) * 3] == bytes(new_width * (DATA['history_rows'] - 1) * 3)


def test_auto_scale_resumes_on_new_publisher_generation():
    _, _, first = snapshot()
    levels = WaterfallLevelController(automatic=True, smoothing=1, update_generations=20)
    assert levels.observe(replace(first, generation=DATA['old_source_generation']))
    changed = replace(first, rows=(replace(first.rows[0], dbm=(-70,) * DATA['width']),))
    assert not levels.observe(replace(changed, generation=1))
    assert levels.observe(replace(changed, generation=DATA['new_source_generation']))
    assert levels.min_dbm == -80
    assert levels.max_dbm == -60


def shell_objects(monkeypatch, keys):
    import kiwi_client.integrated_terminal as shell
    for name in ('mousemask', 'curs_set', 'doupdate'):
        monkeypatch.setattr(shell.curses, name, lambda *args: None)
    monkeypatch.setattr(shell.curses, 'has_colors', lambda: False)
    drawn, events = [], []
    class Screen:
        inputs = iter(keys)
        def get_wch(self): return next(self.inputs)
        def getmaxyx(self): return 40, 160
        def addnstr(self, row, col, text, *args): drawn.append(text)
        def __getattr__(self, name): return lambda *args: None
    class Presenter:
        def finish(self): events.append('finished')
        def __getattr__(self, name): return lambda *args, **kwargs: None
    kwargs = dict(model=WaterfallGuiModel(tuned_khz=0, selected_khz=0),
        presets={}, presenter=Presenter(), levels=WaterfallLevelController(),
        tui_controller=None, tui_config=None, source_fps=20, refresh_hz=10000,
        scale_font_backend='bitmap')
    return shell, Screen(), kwargs, drawn, events


@pytest.mark.parametrize('scenario', ['negative_tune_keys', 'stopped_view_keys'])
def test_tuning_errors_leave_console_running(monkeypatch, scenario):
    shell, screen, kwargs, drawn, events = shell_objects(monkeypatch, DATA[scenario])
    if scenario == 'stopped_view_keys':
        def fail(): raise RuntimeError('synthetic source stopped')
        monkeypatch.setattr(kwargs['model'], 'recenter', fail)
    shell.run_fixture_shell(screen, **kwargs, live_source=None,
        timeline=FixtureWaterfallTimeline.from_fixture(Path('tests/fixtures/kiwi/local-wf-am-855-zoom7.jsonl')))
    assert events == ['finished']
    assert any(('frequency' if scenario == 'negative_tune_keys' else 'synthetic source stopped') in text for text in drawn)
    assert kwargs['model'].session.state.frequency_khz == 0


def test_source_stop_failure_still_restores_terminal_and_checkpoints(monkeypatch):
    shell, screen, kwargs, drawn, events = shell_objects(monkeypatch, ['q'])
    def fail(): raise RuntimeError('synthetic stop failure')
    source = SimpleNamespace(poll_generation=lambda: 0, stop=fail)
    checkpoint = SimpleNamespace(save_if_changed=lambda *args, **kw: events.append('checkpoint') if kw.get('force') else None)
    with pytest.raises(RuntimeError, match='synthetic stop failure'):
        shell.run_fixture_shell(screen, **kwargs, live_source=source, timeline=None, settings_checkpoint=checkpoint)
    assert events == ['finished', 'checkpoint']
