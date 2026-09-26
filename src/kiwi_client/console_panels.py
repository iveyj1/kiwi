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


def main_panel_rows(*, columns: int, height: int, radio: str, station: list[str],
                    reception: list[str], filters: str, help_rows: list[str],
                    message: str, prompt: str = ':', telemetry: str = '', radio_title: str = 'RADIO') -> list[str]:
    """Option A: full-width radio/footer bands and a fixed station/log split."""
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
    split = width >= 73
    body_count = max(2, min(6, height - 8 - int(active_prompt)))
    rows = [rule(width, radio_title, left='╭', right='╮'), row(width, radio)]
    if split:
        rows.append(split_rule(width, 'STATION / CATALOGUE', 'RECEPTION / LOG'))
        for index in range(body_count):
            rows.append(split_row(width, station[index] if index < len(station) else '',
                                  reception[index] if index < len(reception) else ''))
        rows.append(split_rule(width, 'FILTERS', '', middle='┴'))
    else:
        rows.append(rule(width, 'STATION / RECEPTION'))
        compact = [station[0] if station else 'No station selected',
                   reception[0] if reception else 'LOG disabled',
                   *(reception[1:2]), *(station[1:])]
        rows.extend(row(width, text) for text in compact[:body_count])
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
                 rule(width, 'Esc cancels; Enter reviews; y confirms / t tentative', left='╰', right='╯')])
    return rows
