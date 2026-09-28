import curses
import io
import json
from collections import deque
from pathlib import Path

from kiwi_client.terminal_input import ConsoleInput, FocusEvent

FIXTURES = Path(__file__).parents[1] / 'fixtures'
REPORTS = json.loads((FIXTURES / 'terminal/focus-reports.json').read_text())


class InputScreen:
    def __init__(self, keys=()):
        self.keys = deque(keys)

    def get_wch(self):
        if not self.keys:
            raise curses.error()
        return self.keys.popleft()


def test_focus_reports_do_not_leak_brackets_into_scale_keys():
    reader = ConsoleInput()
    screen = InputScreen(REPORTS['out'] + REPORTS['in'] + ['[', 'l'])
    assert reader.read(screen, 0) == FocusEvent.OUT
    assert reader.read(screen, 0) == FocusEvent.IN
    assert reader.read(screen, 0) == '['
    assert reader.read(screen, 0) == 'l'


def test_terminfo_focus_keys_use_names_not_fixed_numeric_codes(monkeypatch):
    names = REPORTS['ncurses_capabilities']
    monkeypatch.setattr(curses, 'keyname', lambda key: {700: names['out'].encode(), 701: names['in'].encode()}[key])
    reader, screen = ConsoleInput(), InputScreen([700, 701])
    assert reader.read(screen, 0) == FocusEvent.OUT
    assert reader.read(screen, 0) == FocusEvent.IN


def test_fragmented_reports_and_escape_timeout_preserve_regular_input():
    reader, screen = ConsoleInput(), InputScreen(['\x1b'])
    assert reader.read(screen, 0) is None
    screen.keys.append('[')
    assert reader.read(screen, .01) is None
    screen.keys.append('O')
    assert reader.read(screen, .02) == FocusEvent.OUT
    screen.keys.extend(['\x1b', 'x', curses.KEY_LEFT])
    assert reader.read(screen, .03) == '\x1b'
    assert reader.read(screen, .03) == 'x'
    assert reader.read(screen, .03) == curses.KEY_LEFT
    screen.keys.append('\x1b')
    assert reader.read(screen, .1) is None
    assert reader.read(screen, .16) == '\x1b'


def test_refresh_deadline_preserves_fast_cadence_but_reserves_input_time():
    from kiwi_client.terminal_input import next_refresh_deadline
    assert next_refresh_deadline(0, .02, 20) == .05
    assert next_refresh_deadline(0, .2, 20) == .25
    assert next_refresh_deadline(0, .049, 20) >= .059


def test_presenter_disables_focus_reports_on_exit():
    from kiwi_client.integrated_terminal import KittyPanePresenter
    output = io.BytesIO()
    presenter = KittyPanePresenter(output=output)
    presenter.set_focus_reporting(True)
    presenter.finish()
    presenter.finish()
    assert output.getvalue() == b'\x1b[?1004h\x1b[?1004l'


def test_focus_pause_latest_resume_and_slow_draw_leave_keyboard_service_time(monkeypatch):
    import kiwi_client.integrated_terminal as shell
    from kiwi_client.gui_app import FixtureWaterfallTimeline, WaterfallGuiModel
    from kiwi_client.waterfall_levels import WaterfallLevelController
    clock = [0.0]
    monkeypatch.setattr(shell.time, 'monotonic', lambda: clock[0])
    monkeypatch.setattr(shell.time, 'sleep', lambda dt: clock.__setitem__(0, clock[0] + dt))
    for name in ('mousemask', 'curs_set', 'doupdate'):
        monkeypatch.setattr(shell.curses, name, lambda *args: None)
    monkeypatch.setattr(shell.curses, 'has_colors', lambda: False)
    events = [None] + REPORTS['out'] + [None] * 40 + REPORTS['in'] + ['l'] * 30 + ['q']
    class Screen(InputScreen):
        polls = 0
        focused = True
        def get_wch(self):
            self.polls += 1
            key = super().get_wch()
            if key == 'O': self.focused = False
            if key == 'I': self.focused = True
            return key
        def getmaxyx(self): return 35, 100
        def __getattr__(self, name): return lambda *args: None
    screen = Screen(events)
    frames = []
    class Presenter:
        def draw(self, image, layout, *, generation):
            assert screen.focused
            frames.append((clock[0], screen.polls, generation))
            clock[0] += .2  # Four times the requested frame period.
        def __getattr__(self, name): return lambda *args, **kwargs: None
    model = WaterfallGuiModel(tuned_khz=855, selected_khz=855, small_step_hz=10)
    levels = WaterfallLevelController()
    timeline = FixtureWaterfallTimeline.from_fixture(FIXTURES / 'kiwi/local-wf-am-855-zoom7.jsonl', repeat=100)
    shell.run_fixture_shell(screen, model=model, timeline=timeline, live_source=None,
        presets={}, presenter=Presenter(), levels=levels, source_fps=20, refresh_hz=20,
        tui_controller=None, tui_config=None,
        scale_font_backend='bitmap')
    assert (levels.min_dbm, levels.max_dbm) == (-100, -40)
    assert abs(model.session.state.frequency_khz - 855.3) < 1e-6
    assert 3 <= len(frames) < 8
    assert frames[1][2] > frames[0][2] + 1  # Source progressed while presentation paused.
    for previous, current in zip(frames[1:], frames[2:]):
        assert current[0] - previous[0] >= .25 - 1e-9
        assert current[1] - previous[1] >= 9  # Not one key per slow frame.
