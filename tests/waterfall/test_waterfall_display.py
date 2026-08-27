"""Pure tests for the shared waterfall display model, palette, and pane cells."""

import pytest

from kiwi_client.waterfall_display import (
    DEFAULT_LEVELS,
    HALF_BLOCK,
    HalfBlockCell,
    WaterfallImageBuffer,
    buffer_from_frames,
    dbm_to_level,
    half_block_cells,
)
from kiwi_client.waterfall_palette import (
    PALETTE_LEVELS,
    cube_index,
    pair_number,
    palette_color,
    palette_indices,
    required_pairs,
)
from kiwi_client.waterfall_pane import draw_waterfall_pane, init_waterfall_pairs, pane_cells


class FakeWindow:
    """Records addstr calls so drawing can be checked without a terminal."""

    def __init__(self):
        self.calls = []

    def addstr(self, y, x, text, attr):
        self.calls.append((y, x, text, attr))


# --- level quantisation ---


def test_dbm_to_level_spans_the_range_and_clamps():
    assert dbm_to_level(-110, min_dbm=-110, max_dbm=-20, levels=10) == 0
    assert dbm_to_level(-20, min_dbm=-110, max_dbm=-20, levels=10) == 9
    assert dbm_to_level(-200, min_dbm=-110, max_dbm=-20, levels=10) == 0
    assert dbm_to_level(0, min_dbm=-110, max_dbm=-20, levels=10) == 9


def test_dbm_to_level_is_monotonic():
    values = [dbm_to_level(v, min_dbm=-110, max_dbm=-20, levels=24) for v in range(-110, -19)]
    assert values == sorted(values)


def test_dbm_to_level_rejects_bad_scales():
    with pytest.raises(ValueError, match="at least two levels"):
        dbm_to_level(-50, levels=1)
    with pytest.raises(ValueError, match="max_dbm must be greater"):
        dbm_to_level(-50, min_dbm=0, max_dbm=-10)


# --- buffer ---


def test_buffer_keeps_newest_first_and_drops_oldest():
    buffer = WaterfallImageBuffer(max_rows=3)
    for value in range(5):
        buffer.append([float(value)])

    assert len(buffer) == 3
    assert [row[0] for row in buffer.rows()] == [4.0, 3.0, 2.0]


def test_buffer_fixes_width_on_first_row_and_rejects_mismatches():
    buffer = WaterfallImageBuffer()
    assert buffer.width is None
    buffer.append([1.0, 2.0, 3.0])

    assert buffer.width == 3
    with pytest.raises(ValueError, match="does not match buffer width"):
        buffer.append([1.0, 2.0])


def test_buffer_applies_calibration_offset():
    buffer = WaterfallImageBuffer()
    buffer.append([-100.0], calibration_db=-13.0)

    assert buffer.rows()[0][0] == -113.0


def test_buffer_rejects_empty_rows_and_bad_sizes():
    with pytest.raises(ValueError, match="at least one row"):
        WaterfallImageBuffer(max_rows=0)
    with pytest.raises(ValueError, match="width must be >= 1"):
        WaterfallImageBuffer(width=0)
    with pytest.raises(ValueError, match="empty waterfall row"):
        WaterfallImageBuffer().append([])


def test_buffer_clear_keeps_width():
    buffer = WaterfallImageBuffer()
    buffer.append([1.0, 2.0])
    buffer.clear()

    assert len(buffer) == 0
    assert buffer.width == 2


def test_buffer_from_frames_preserves_fixture_order_as_newest_last():
    buffer = buffer_from_frames([[1.0], [2.0], [3.0]])

    # Fixtures store oldest-first; the buffer reports newest-first.
    assert [row[0] for row in buffer.rows()] == [3.0, 2.0, 1.0]


# --- half-block cells ---


def test_half_block_cells_pairs_two_rows_per_cell():
    cells = half_block_cells([(0, 1), (2, 3)])

    assert cells == ((HalfBlockCell(0, 2), HalfBlockCell(1, 3)),)


def test_half_block_cells_pads_a_partial_buffer():
    cells = half_block_cells([(5, 5)], height=2, fill=0)

    assert cells[0] == (HalfBlockCell(5, 0), HalfBlockCell(5, 0))
    assert cells[1] == (HalfBlockCell(0, 0), HalfBlockCell(0, 0))


def test_half_block_cells_rejects_ragged_rows():
    with pytest.raises(ValueError, match="not rectangular"):
        half_block_cells([(1, 2), (1,)])


def test_half_block_character_is_the_upper_block():
    assert HALF_BLOCK == "▀"


# --- palette ---


def test_cube_index_matches_the_xterm_256_formula():
    assert cube_index(0, 0, 0) == 16
    assert cube_index(5, 5, 5) == 231
    with pytest.raises(ValueError, match="red must be in range"):
        cube_index(6, 0, 0)


def test_palette_runs_dark_to_hot_within_the_colour_cube():
    indices = palette_indices()

    assert len(indices) == PALETTE_LEVELS
    assert indices[0] == 16, "lowest level should be black"
    assert indices[-1] == 231, "highest level should be white"
    assert all(16 <= index <= 231 for index in indices)


def test_palette_resamples_for_a_different_level_count():
    small = palette_indices(8)

    assert len(small) == 8
    assert small[0] == 16 and small[-1] == 231


def test_palette_rejects_out_of_range_levels():
    with pytest.raises(ValueError, match="outside 0"):
        palette_color(PALETTE_LEVELS)


def test_pair_numbers_are_unique_and_skip_reserved_pair_zero():
    numbers = {pair_number(u, l) for u in range(PALETTE_LEVELS) for l in range(PALETTE_LEVELS)}

    assert len(numbers) == PALETTE_LEVELS**2
    assert 0 not in numbers
    assert max(numbers) < required_pairs()


def test_required_pairs_fits_the_terminals_in_use():
    # Local terminals report 32767 pairs or more.
    assert required_pairs(DEFAULT_LEVELS) < 32767


# --- pane ---


def test_pane_cells_shows_two_frames_per_character_row():
    buffer = buffer_from_frames([[float(-100 + i)] * 64 for i in range(8)])

    cells = pane_cells(buffer, width=16, height=3)

    assert len(cells) == 3
    assert len(cells[0]) == 16


def test_pane_cells_reduces_bins_to_pane_width():
    buffer = buffer_from_frames([[-100.0] * 1024])

    cells = pane_cells(buffer, width=80, height=1)

    assert len(cells[0]) == 80


def test_pane_cells_is_empty_without_data():
    assert pane_cells(WaterfallImageBuffer(), width=10, height=2) == ()


def test_pane_cells_rejects_bad_geometry():
    buffer = buffer_from_frames([[-100.0] * 8])
    with pytest.raises(ValueError, match="width must be >= 1"):
        pane_cells(buffer, width=0, height=1)


def test_pane_cells_max_reduction_keeps_a_narrow_carrier_visible():
    """A single hot bin must survive reduction to pane width."""
    row = [-100.0] * 1024
    row[700] = -20.0
    buffer = buffer_from_frames([row])

    cells = pane_cells(buffer, width=100, height=1, min_dbm=-100, max_dbm=-20)

    assert max(cell.upper for cell in cells[0]) == DEFAULT_LEVELS - 1


def test_init_waterfall_pairs_registers_every_combination():
    registered = []
    count = init_waterfall_pairs(lambda n, f, b: registered.append((n, f, b)), levels=4)

    assert count == 16
    assert len(registered) == 16
    assert len({n for n, _, _ in registered}) == 16


def test_init_waterfall_pairs_refuses_a_terminal_with_too_few_pairs():
    with pytest.raises(RuntimeError, match="colour pairs"):
        init_waterfall_pairs(lambda n, f, b: None, levels=24, max_pairs=100)


def test_draw_waterfall_pane_groups_runs_into_single_calls():
    """Identical adjacent cells should become one addstr, not one per cell."""
    row = tuple(HalfBlockCell(3, 4) for _ in range(20))
    window = FakeWindow()

    drawn = draw_waterfall_pane(window, [row], top=2, color_pair=lambda p: p)

    assert drawn == 1
    assert len(window.calls) == 1
    y, x, text, _ = window.calls[0]
    assert (y, x) == (2, 0)
    assert text == HALF_BLOCK * 20


def test_draw_waterfall_pane_splits_on_colour_change():
    row = (HalfBlockCell(1, 1), HalfBlockCell(1, 1), HalfBlockCell(2, 2))
    window = FakeWindow()

    draw_waterfall_pane(window, [row], top=0, color_pair=lambda p: p)

    assert [call[2] for call in window.calls] == [HALF_BLOCK * 2, HALF_BLOCK]


def test_draw_waterfall_pane_survives_a_curses_write_error():
    """curses raises on the window's last cell; the pane must not crash the TUI."""

    class Failing(FakeWindow):
        def addstr(self, y, x, text, attr):
            raise Exception("addstr() returned ERR")

    drawn = draw_waterfall_pane(Failing(), [(HalfBlockCell(0, 0),)], top=0, color_pair=lambda p: p)

    assert drawn == 1
