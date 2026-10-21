"""Receiver picker state and text geometry, independent of terminal/network I/O."""
from dataclasses import dataclass

from kiwi_client.console_panels import fit, rule
from kiwi_client.tui import REGISTER_KEYS, receiver_for_register, sorted_receiver_registers


@dataclass
class ReceiverPopup:
    entries: list[tuple[str, str, str]]
    current: str
    index: int = 0

    @classmethod
    def open(cls, config, controller):
        if controller.receiver_presets:
            entries = [(key, receiver_for_register(key, config, controller), item['description'])
                       for key, item in sorted_receiver_registers(controller.receiver_presets)]
        else:
            entries = [(REGISTER_KEYS[i], address, '')
                       for i, address in enumerate(config.receivers.allowed[:len(REGISTER_KEYS)])]
        current = controller.state.receiver
        index = next((i for i, (_, address, _) in enumerate(entries) if address == current), 0)
        return cls(entries, current, index)

    def move(self, delta):
        self.index = max(0, min(max(0, len(self.entries) - 1), self.index + delta))

    @property
    def selected_register(self):
        return self.entries[self.index][0] if self.entries else None

    def lines(self, columns, available_rows):
        width = max(4, min(78, columns - 2))
        height = max(4, min(14, available_rows))
        capacity = height - 3
        start = max(0, min(self.index - capacity // 2, len(self.entries) - capacity))
        def row(text):
            return '│' + fit(text, width - 2) + '│'
        rows = [rule(width, 'Receivers — * current', left='╭', right='╮')]
        for i in range(start, start + capacity):
            if i >= len(self.entries):
                rows.append(row(''))
            else:
                key, address, description = self.entries[i]
                rows.append(row(f"{'>' if i == self.index else ' '} {'*' if address == self.current else ' '} {key} {address} {description}"))
        position = f'{self.index + 1}/{len(self.entries)}' if self.entries else 'empty'
        rows.append(row(f'{position} ↑↓ Enter select Esc cancel'))
        rows.append('╰' + '─' * (width - 2) + '╯')
        return rows
