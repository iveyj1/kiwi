"""Read-only terminal cell metrics; no escape queries or input consumption."""
from dataclasses import dataclass
import fcntl
import struct
import termios


@dataclass(frozen=True)
class TerminalCellPixels:
    width: int = 8
    height: int = 16
    measured: bool = False


def terminal_cell_pixels(columns: int, lines: int) -> TerminalCellPixels:
    """Prefer matching tty pixel dimensions; otherwise assume stable 8x16 cells."""
    if columns <= 0 or lines <= 0:
        raise ValueError('terminal dimensions must be positive')
    for descriptor in (1, 0, 2):
        try:
            rows, cols, width, height = struct.unpack('HHHH', fcntl.ioctl(descriptor, termios.TIOCGWINSZ, b'\0' * 8))
        except (OSError, struct.error):
            continue
        if (cols, rows) == (columns, lines) and width >= cols and height >= rows:
            return TerminalCellPixels(width // cols, height // rows, True)
    return TerminalCellPixels()
