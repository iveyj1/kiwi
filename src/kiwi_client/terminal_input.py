"""Decode xterm focus reports without leaking their bytes into console keymaps."""
from collections import deque
from enum import Enum
import curses


def next_refresh_deadline(started: float, finished: float, refresh_hz: float) -> float:
    """Keep normal cadence, but reserve input time instead of chasing late frames."""
    period = 1.0 / refresh_hz
    if finished - started >= period:
        return finished + period
    return max(started + period, finished + min(0.01, period))


class FocusEvent(Enum):
    IN = 'focus-in'
    OUT = 'focus-out'


class ConsoleInput:
    def __init__(self, escape_timeout=0.05):
        self.escape_timeout = escape_timeout
        self.pending = deque()
        self.prefix = []
        self.deadline = 0.0

    def read(self, screen, now):
        if self.prefix and now >= self.deadline:
            self.pending.extend(self.prefix)
            self.prefix = []
        if self.pending:
            return self.pending.popleft()
        # Read at most one key or one three-byte focus report per call.
        for _ in range(3):
            try:
                key = screen.get_wch()
            except curses.error:
                return None
            if isinstance(key, int):
                # Kitty terminfo can decode focus reports to extended ncurses keys.
                # Their numeric codes are installation-dependent; use capability names.
                try:
                    name = curses.keyname(key)
                except curses.error:
                    name = b''
                if name in (b'kxIN', b'kxOUT'):
                    return FocusEvent.IN if name == b'kxIN' else FocusEvent.OUT
            if not self.prefix:
                if key != '\x1b':
                    return key
                self.prefix = [key]
                self.deadline = now + self.escape_timeout
                continue
            self.prefix.append(key)
            if self.prefix == ['\x1b', '[']:
                continue
            if self.prefix in (['\x1b', '[', 'I'], ['\x1b', '[', 'O']):
                event = FocusEvent.IN if key == 'I' else FocusEvent.OUT
                self.prefix = []
                return event
            self.pending.extend(self.prefix)
            self.prefix = []
            return self.pending.popleft()
        return None
