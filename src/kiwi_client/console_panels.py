"""Pure cell-aligned Unicode console panels; no terminal or receiver operations."""
from __future__ import annotations

import unicodedata


def cell_width(text: str) -> int:
    return sum(0 if unicodedata.combining(c) else 2 if unicodedata.east_asian_width(c) in {'W', 'F'} else 1 for c in text)


def fit(text: str, width: int, *, tail: bool = False) -> str:
    if width <= 0:
        return ''
    text = ''.join(c if c.isprintable() or unicodedata.combining(c) else ' ' for c in str(text))
    if cell_width(text) > width:
        available = max(0, width - 1)
        result = ''
        for c in (reversed(text) if tail else text):
            if cell_width(result + c) > available:
                break
            result = (c + result) if tail else (result + c)
        text = ('…' + result) if tail else (result + '…')
    return text + ' ' * max(0, width - cell_width(text))


def rule(width: int, title: str = '', *, left='├', right='┤') -> str:
    inside = '─' * (width - 2)
    if title:
        label = fit(' ' + title + ' ', max(1, width - 4)).rstrip() + ' '
        inside = '─' + label + '─' * max(0, width - 3 - cell_width(label))
    return left + inside + right


def row(width: int, text: str, *, tail=False) -> str:
    return '│ ' + fit(text, width - 4, tail=tail) + ' │'


def split_widths(width: int):
    left = (width - 3) // 2
    return left, width - 3 - left


def split_row(width: int, first: str, second: str) -> str:
    left, right = split_widths(width)
    return '│ ' + fit(first, left - 2) + ' │ ' + fit(second, right - 2) + ' │'


def split_rule(width: int, first: str, second: str, *, middle='┬') -> str:
    left, right = split_widths(width)
    def part(text, size):
        if not text:
            return '─' * size
        label = fit(' ' + text + ' ', size).rstrip()
        if cell_width(label) < size:
            label += ' '
        return label + '─' * (size - cell_width(label))
    return '├' + part(first, left) + middle + part(second, right) + '┤'


def station_table_lines(table, width: int, count: int) -> list[str]:
    """Cell-aligned full-width spreadsheet; reduce columns on narrow terminals."""
    if width >= 110:
        fields, sizes = [0, 1, 2, 3, 4, 5, 6], [8, 12, 31, width - 99, 11, 9, 10]
    elif width >= 80:
        fields, sizes = [0, 1, 2, 3, 4, 5, 6], [7, 11, 12, width - 74, 8, 8, 10]
    elif width >= 52:
        fields, sizes = [0, 1, 2, 3, 5], [7, 9, 12, width - 48, 8]
    else:
        fields, sizes = [0, 1, 2], [6, 8, width - 20]
    headers = ('ID', 'Nominal kHz', 'Logged (UTC)', 'Location', 'Distance km', 'Period s', 'Last (RNA)')
    def render(values):
        return ' │ '.join(fit(values[field], size) for field, size in zip(fields, sizes))
    selected = next((i for i, values in enumerate(table) if values[0].startswith('> ')), 0)
    capacity = max(0, count - 1)
    start = max(0, min(selected - capacity // 2, len(table) - capacity))
    return [render(headers), *(render(values) for values in table[start:start + capacity])][:count]


def main_panel_rows(*, columns: int, height: int, radio: str, station: list[str],
                    reception: list[str], filters: str, help_rows: list[str],
                    message: str, prompt: str = ':', telemetry: str = '', radio_title: str = 'RADIO',
                    table: list[tuple[str, ...]] | None = None, table_title: str = 'STATIONS') -> list[str]:
    """Full-width radio, compact station spreadsheet, and filter/help bands."""
    width = max(12, columns - 1)  # Leave curses' final column unused, including borders.
    active_prompt = prompt != ':'
    if height < 10 + int(active_prompt):
        # Small terminals keep identity, logging and input/error visible, not telemetry.
        body = [station[0] if station else radio, reception[0] if reception else radio,
                *station[1:2], 'Message: ' + message]
        if active_prompt:
            body = body[:max(0, height - 3)] + [prompt]
        else:
            body = body[:max(0, height - 2)]
        return [rule(width, 'RADIO / STATION', left='╭', right='╮'),
                *(row(width, text, tail=text == prompt) for text in body),
                rule(width, left='╰', right='╯')][:height]
    body_count = max(2, min(6, height - 8 - int(active_prompt)))
    rows = [rule(width, radio_title, left='╭', right='╮'), row(width, radio)]
    rows.append(rule(width, table_title))
    if table:
        body = station_table_lines(table, width - 4, body_count)
    else:
        body = [station[0] if station else 'No station selected',
                reception[0] if reception else 'LOG disabled', *station[1:]]
    rows.extend(row(width, text) for text in body[:body_count])
    rows.append(rule(width, 'FILTERS'))
    rows.append(row(width, filters))
    rows.append(row(width, 'KEYS ' + (help_rows[0] if help_rows else '')))
    # More room exposes additional help and telemetry, without moving the column divider.
    remaining = height - len(rows) - 2 - int(active_prompt)
    for text in [*help_rows[1:], telemetry]:
        if remaining <= 0:
            break
        if text:
            rows.append(row(width, text))
            remaining -= 1
    rows.append(row(width, 'Message: ' + message))
    if active_prompt:
        rows.append(row(width, prompt, tail=True))
    rows.append(rule(width, left='╰', right='╯'))
    return rows


def log_panel_rows(*, columns: int, height: int, title: str, editable: list[str],
                   evidence: list[str], prompt: str, message: str, history: str) -> list[str]:
    """Option B: editable fields left, frozen reception evidence right."""
    width = max(12, columns - 1)
    rows = [rule(width, title, left='╭', right='╮')]
    if width >= 73:
        rows.append(split_rule(width, 'EDITABLE', 'RECORDED EVIDENCE (read only)'))
        count = max(1, min(max(len(editable), len(evidence)), height - 8))
        for index in range(count):
            rows.append(split_row(width, editable[index] if index < len(editable) else '',
                                  evidence[index] if index < len(evidence) else ''))
        rows.append(split_rule(width, 'HISTORY', '', middle='┴'))
    else:
        rows.append(rule(width, 'EDITABLE / RECORDED EVIDENCE'))
        count = max(1, height - 8)
        rows.extend(row(width, text) for text in [*editable, *evidence][:count])
        rows.append(rule(width, 'HISTORY'))
    rows.extend([row(width, history), rule(width, 'EDIT / SAVE'),
                 row(width, prompt, tail=True), row(width, message),
                 rule(width, 'Esc cancels; Enter reviews; y yes / t tentative / n not heard / d delete', left='╰', right='╯')])
    return rows
