"""Main-page reception drafts: freeze evidence at entry, save only explicitly."""
from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path

from kiwi_client.ndb_logbook import Logbook, reception_draft, validate_reception


@dataclass
class QuickLogEntry:
    draft: dict
    original: dict | None

    @classmethod
    def open(cls, browser, state, *, receiver, source_kind, event, existing=None):
        # Validate current selection/tuning even when updating an earlier hearing.
        current = reception_draft(browser, state, receiver=receiver, source_kind=source_kind, event=event)
        if existing is not None:
            if any(existing.get(key) != current.get(key)
                   for key in ('station_key', 'receiver', 'source_kind', 'event')):
                raise ValueError('existing reception does not match selected station/log scope')
            return cls(deepcopy(existing), deepcopy(existing))
        current['status'] = 'confirmed'
        return cls(current, None)

    def toggle_status(self):
        self.draft['status'] = 'tentative' if self.draft['status'] == 'confirmed' else 'confirmed'

    def save(self, path: Path) -> str:
        validate_reception(self.draft)
        with Logbook(path) as book:
            if self.original is not None:
                key = self.original['log_id']
                book.revise(key, status=self.draft['status'], notes=self.draft['notes'], expected=self.original)
                return f"Updated {self.draft['ident']} {self.draft['status']} log #{key}; original time/tuning retained"
            key, duplicates = book.save(self.draft)
        return f"Saved {self.draft['ident']} {self.draft['status']} log #{key}; {duplicates} previous station/event entries"
