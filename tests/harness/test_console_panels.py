import pytest

from kiwi_client.console_panels import cell_width, fit, main_panel_rows, log_panel_rows, split_widths


@pytest.mark.parametrize('columns', [40, 80, 100, 160])
@pytest.mark.parametrize('height', [5, 10, 11, 19])
@pytest.mark.parametrize('prompt', [':', ':rna range 2000_'])
def test_main_panel_fits_and_preserves_fixed_boundaries(columns, height, prompt):
    rows = main_panel_rows(columns=columns, height=height, radio='CW 378.405 kHz BW50',
        station=['RJ / 378 kHz', 'USB 378.405 kHz', '450 km / 500 W / active', 'A very long location ' * 10],
        reception=['CONFIRMED 2026-09-26 01:02:03Z', '#17 / 2 entries', 'CLE332 / live'],
        filters='range<=2000 power>=100', help_rows=['n/N station w edit W new', 'More keys'],
        message='Save successful', prompt=prompt)
    assert len(rows) <= height
    assert rows[0].startswith('╭') and rows[-1].endswith('╯')
    assert all(cell_width(row) == columns - 1 for row in rows)
    assert any('RJ' in row for row in rows)
    assert any('CONFIRMED' in row for row in rows)
    if prompt != ':':
        assert any(prompt in row for row in rows)
    if columns >= 80:
        separator = split_widths(columns - 1)[0] + 1
        for row in rows:
            if row.count('│') == 3:
                assert row[separator] == '│'


@pytest.mark.parametrize('columns', [40, 80, 100, 160])
@pytest.mark.parametrize('height', [12, 24, 40])
def test_logging_layout_has_fixed_columns_and_visible_actions(columns, height):
    rows = log_panel_rows(columns=columns, height=height, title='EDIT LOG #17 / RJ',
        editable=['UTC 2026-09-26 01:02:03', 'Status CONFIRMED', 'Notes ' + 'long ' * 200],
        evidence=['Nominal 378 kHz', 'RF center 378.405 kHz', 'BW 50 Hz', 'Receiver fixture'],
        prompt='UTC | notes: ' + 'x' * 300 + '_', message='failed write; retry', history='CONFIRMED yesterday')
    assert len(rows) <= height
    assert all(cell_width(row) == columns - 1 for row in rows)
    assert any('failed write' in row for row in rows)
    assert any('_ │' in row for row in rows)  # Long input scrolls left, keeping insertion end visible.
    assert rows[-1].endswith('╯')
    if columns >= 80:
        assert any('EDITABLE' in row and 'RECORDED EVIDENCE' in row for row in rows)


def test_current_example_generator_is_aligned_and_never_overwrites_edits(tmp_path):
    import runpy
    module = runpy.run_path('tools/render_console_examples.py')
    path = tmp_path / 'examples.txt'
    assert module['main'](['--output', str(path)]) == 0
    text = path.read_text()
    assert 'NOT-HEARD' in text and 'DELETE #17 PH' in text
    assert 'STATION / CATALOGUE' in text and 'RECORDED EVIDENCE' in text
    for row in text.splitlines():
        if row.startswith(('│', '╭', '╰', '├')):
            assert cell_width(row) == 99
    path.write_text('my layout tweaks')
    with pytest.raises(FileExistsError):
        module['main'](['--output', str(path)])
    assert path.read_text() == 'my layout tweaks'


def test_display_cells_combining_wide_characters_and_controls():
    assert cell_width('Chibougamau') == 11
    assert cell_width('e\u0301東京') == 5
    assert cell_width(fit('e\u0301東京' * 30, 20)) == 20
    assert cell_width(fit('e\u0301東京' * 30, 20, tail=True)) == 20
    assert '\x1b' not in fit('bad\x1b[2J', 20)
    rows = main_panel_rows(columns=100, height=11, radio='radio', station=['東京 e\u0301' * 20],
        reception=['CONFIRMED'], filters='all', help_rows=['keys'], message='ok')
    separator = split_widths(99)[0] + 1
    for row in rows:
        if row.count('│') == 3:
            second = row.index('│', 1)
            assert cell_width(row[:second]) == separator
            assert cell_width(row) == 99
