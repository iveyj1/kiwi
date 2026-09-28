"""Standalone desktop log browser. No receiver connection or write-through cells."""
from __future__ import annotations

import argparse
from dataclasses import asdict
from datetime import date
import json
import os
from pathlib import Path
import tempfile

from kiwi_client.log_browser_data import BrowserFilter, LogWorkspace, NativeLogSource, StagedLogSource

COLUMNS = ('UTC', 'ID', 'kHz', 'Location', 'Country', 'Region', 'km', 'Receiver / setup',
           'Status', 'Notes', 'Source', 'Event', 'Review flags')


def cells(record):
    stamp = record.heard_utc.replace('T', ' ').removesuffix('Z')
    if record.precision == 'minute': stamp = stamp[:16]
    return (stamp, record.ident, f'{record.frequency_khz:g}' if record.frequency_khz else '?',
            record.location, record.country, record.region,
            '?' if record.distance_km is None else f'{record.distance_km:.0f}',
            record.receiver, record.status, record.notes, record.source, record.event, '; '.join(record.flags))


def reception_summary(record):
    raw = json.loads(record.evidence_json)
    tuning = ''
    if 'rf_center_khz' in raw:
        tuning = f'\nRecorded RF center: {raw["rf_center_khz"]} kHz; bandwidth: {raw.get("bandwidth_hz", "?")} Hz'
    signal = raw.get('log', {}).get('SignalStrength', '').strip()
    comments = raw.get('station', {}).get('GenNotes', '').strip()
    basis = raw.get('distance_basis', 'frozen native distance' if record.source.startswith('Native') else 'see report evidence')
    return (f'{record.ident}   {record.frequency_khz:g} kHz   |   {cells(record)[0]} UTC ({record.precision} precision)\n'
            f'{record.location}   {record.region} {record.country}\n'
            f'Receiver / setup: {record.receiver}\n'
            f'Status: {record.status}   |   Source: {record.source}   |   Event: {record.event or "none"}\n'
            f'Distance: {cells(record)[6]} km ({basis})   |   Signal: {signal or "not recorded"}' + tuning +
            f'\n\nNotes: {record.notes or "—"}' + (f'\nCatalogue notes: {comments}' if comments else '') +
            '\n\n' + ('Review:\n' + '\n'.join('• ' + flag for flag in record.flags) if record.flags else 'No staging review flags.') +
            f'\n\nSource record: {record.reference.path}\nKey: {record.reference.key}\n'
            'Original fields, backup versions and report evidence are in the Source / raw evidence tab.')


def save_views(path: Path, views: dict):
    content = json.dumps(dict(schema=1, views=views), indent=2, allow_nan=False) + '\n'
    path.parent.mkdir(parents=True, exist_ok=True)
    name = None
    try:
        with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', dir=path.parent, delete=False) as stream:
            name = stream.name
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(name, path)
    finally:
        if name and os.path.exists(name): os.unlink(name)


def create_window(workspace: LogWorkspace, *, settings_path: Path | None = None):
    from PySide6 import QtCore, QtGui, QtWidgets
    Qt = QtCore.Qt

    class TableModel(QtCore.QAbstractTableModel):
        def __init__(self):
            super().__init__()
            self.records = ()
        def rowCount(self, parent=QtCore.QModelIndex()): return 0 if parent.isValid() else len(self.records)
        def columnCount(self, parent=QtCore.QModelIndex()): return 0 if parent.isValid() else len(COLUMNS)
        def data(self, index, role=Qt.ItemDataRole.DisplayRole):
            if not index.isValid(): return None
            record = self.records[index.row()]
            if role == Qt.ItemDataRole.DisplayRole: return cells(record)[index.column()]
            if role == Qt.ItemDataRole.ToolTipRole:
                return '\n'.join(record.flags) or f'{record.source}: {record.reference.key}'
            if role == Qt.ItemDataRole.UserRole: return record.id
            if record.flags and index.column() == 8:
                if role == Qt.ItemDataRole.BackgroundRole: return QtGui.QColor('#fff0bd')
                if role == Qt.ItemDataRole.ForegroundRole: return QtGui.QColor('#202020')
            return None
        def headerData(self, section, orientation, role=Qt.ItemDataRole.DisplayRole):
            if role == Qt.ItemDataRole.DisplayRole and orientation == Qt.Orientation.Horizontal:
                return COLUMNS[section]
            return None
        def flags(self, index):
            return Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable
        def refresh(self):
            self.beginResetModel()
            self.records = workspace.records
            self.endResetModel()

    class Proxy(QtCore.QSortFilterProxyModel):
        def __init__(self):
            super().__init__()
            self.filters = BrowserFilter()
        def filterAcceptsRow(self, row, parent):
            return self.filters.matches(self.sourceModel().records[row])
        def lessThan(self, left, right):
            a, b = (self.sourceModel().records[index.row()] for index in (left, right))
            column = left.column()
            if column == 0: return (a.heard_utc, a.id) < (b.heard_utc, b.id)
            if column == 2: return a.frequency_khz < b.frequency_khz
            if column == 6:
                return (a.distance_km is None, a.distance_km or 0) < (b.distance_km is None, b.distance_km or 0)
            return cells(a)[column].casefold() < cells(b)[column].casefold()

    class Window(QtWidgets.QMainWindow):
        def __init__(self):
            super().__init__()
            self.setWindowTitle('Kiwi Logbook — read-only review')
            self.resize(1450, 850)
            self.station_key = ''
            self.history_previous = None
            self.custom_views = {}
            self.settings_error = ''
            if settings_path is not None and settings_path.exists():
                try:
                    saved = json.loads(settings_path.read_text(encoding='utf-8'))
                    if saved.get('schema') != 1 or not isinstance(saved.get('views'), dict):
                        raise ValueError('unsupported saved views')
                    for name, fields in saved['views'].items(): BrowserFilter(**fields)
                    self.custom_views = saved['views']
                except (OSError, ValueError, TypeError) as exc:
                    self.settings_error = str(exc)
            body = QtWidgets.QWidget()
            self.setCentralWidget(body)
            layout = QtWidgets.QVBoxLayout(body)
            toolbar = QtWidgets.QHBoxLayout()
            self.view = QtWidgets.QComboBox()
            self.view.addItems(['All receptions', 'Needs review', 'Tentative', *self.custom_views])
            toolbar.addWidget(QtWidgets.QLabel('View'))
            toolbar.addWidget(self.view)
            for text, action in [('Save view…', self.save_view), ('Add source…', self.add_source),
                                 ('Reload', self.reload), ('Station history', self.show_history),
                                 ('Back', self.back), ('Clear filters', self.clear_filters)]:
                button = QtWidgets.QPushButton(text)
                button.clicked.connect(action)
                toolbar.addWidget(button)
            toolbar.addStretch()
            layout.addLayout(toolbar)
            filters = QtWidgets.QGridLayout()
            self.search = QtWidgets.QLineEdit()
            self.search.setPlaceholderText('Search ID, location, notes… Use id:CH for exact ID (Ctrl+F)')
            self.source = QtWidgets.QComboBox()
            self.status = QtWidgets.QComboBox()
            self.event = QtWidgets.QComboBox()
            self.date_from = QtWidgets.QLineEdit()
            self.date_to = QtWidgets.QLineEdit()
            self.date_from.setPlaceholderText('YYYY-MM-DD or blank')
            self.date_to.setPlaceholderText('YYYY-MM-DD or blank')
            self.minimum = QtWidgets.QDoubleSpinBox()
            self.maximum = QtWidgets.QDoubleSpinBox()
            for spin in (self.minimum, self.maximum):
                spin.setRange(0, 1000000)
                spin.setDecimals(3)
                spin.setSpecialValueText('Any')
            self.review = QtWidgets.QCheckBox('Review flags only')
            filters.addWidget(self.search, 0, 0, 1, 4)
            for col, (label, widget) in enumerate((('Source', self.source), ('Status', self.status), ('Event', self.event))):
                filters.addWidget(QtWidgets.QLabel(label), 0, 4 + col * 2)
                filters.addWidget(widget, 0, 5 + col * 2)
            for col, (label, widget) in enumerate((('From UTC', self.date_from), ('Through UTC', self.date_to),
                                                  ('Min kHz', self.minimum), ('Max kHz', self.maximum))):
                filters.addWidget(QtWidgets.QLabel(label), 1, col * 2)
                filters.addWidget(widget, 1, col * 2 + 1)
            filters.addWidget(self.review, 1, 8, 1, 2)
            layout.addLayout(filters)
            self.context = QtWidgets.QLabel('')
            self.context.setTextFormat(Qt.TextFormat.PlainText)
            layout.addWidget(self.context)
            splitter = QtWidgets.QSplitter(Qt.Orientation.Vertical)
            self.table = QtWidgets.QTableView()
            self.model = TableModel()
            self.proxy = Proxy()
            self.proxy.setSourceModel(self.model)
            self.table.setModel(self.proxy)
            self.table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectionBehavior.SelectRows)
            self.table.setSelectionMode(QtWidgets.QAbstractItemView.SelectionMode.SingleSelection)
            self.table.setEditTriggers(QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
            self.table.setSortingEnabled(True)
            self.table.setAlternatingRowColors(True)
            self.table.verticalHeader().hide()
            self.table.horizontalHeader().setSectionsMovable(True)
            for col, width in enumerate((160, 65, 65, 240, 65, 60, 65, 200, 95, 220, 150, 90, 260)):
                self.table.setColumnWidth(col, width)
            splitter.addWidget(self.table)
            tabs = QtWidgets.QTabWidget()
            self.details = QtWidgets.QPlainTextEdit()
            self.details.setReadOnly(True)
            self.raw_details = QtWidgets.QPlainTextEdit()
            self.raw_details.setReadOnly(True)
            tabs.addTab(self.details, 'Reception')
            tabs.addTab(self.raw_details, 'Source / raw evidence')
            splitter.addWidget(tabs)
            splitter.setSizes([570, 200])
            layout.addWidget(splitter)
            self.notice = QtWidgets.QLabel('')
            self.notice.setWordWrap(True)
            self.notice.setTextFormat(Qt.TextFormat.PlainText)
            layout.addWidget(self.notice)
            self.table.selectionModel().selectionChanged.connect(self.selection_changed)
            self.table.doubleClicked.connect(lambda *_: self.show_history())
            for widget in (self.search, self.date_from, self.date_to): widget.textChanged.connect(self.apply_filters)
            for widget in (self.source, self.status, self.event): widget.currentIndexChanged.connect(self.apply_filters)
            for widget in (self.minimum, self.maximum): widget.valueChanged.connect(self.apply_filters)
            self.review.toggled.connect(self.apply_filters)
            self.view.activated.connect(self.choose_view)
            for key, action in [('Ctrl+F', self.search.setFocus), ('F5', self.reload)]:
                shortcut = QtGui.QShortcut(QtGui.QKeySequence(key), self)
                shortcut.activated.connect(action)
            self.reload()
            self.table.sortByColumn(0, Qt.SortOrder.DescendingOrder)

        def filter_state(self):
            return BrowserFilter(search=self.search.text(), source=self.source.currentData() or '',
                status=self.status.currentData() or '', event=self.event.currentData() or '',
                date_from=self.date_from.text().strip(), date_to=self.date_to.text().strip(),
                minimum_khz=self.minimum.value() or None, maximum_khz=self.maximum.value() or None,
                station_key=self.station_key, review_only=self.review.isChecked())

        def apply_filters(self, *_):
            filters = self.filter_state()
            try:
                for value in (filters.date_from, filters.date_to):
                    if value and date.fromisoformat(value).isoformat() != value: raise ValueError('use YYYY-MM-DD')
                if filters.date_from and filters.date_to and filters.date_from > filters.date_to:
                    raise ValueError('date range is reversed')
                if filters.minimum_khz and filters.maximum_khz and filters.minimum_khz > filters.maximum_khz:
                    raise ValueError('frequency range is reversed')
            except ValueError as exc:
                self.notice.setText(f'Filter not applied: {exc}')
                return
            if hasattr(self.proxy, 'endFilterChange'):
                self.proxy.beginFilterChange()
                self.proxy.filters = filters
                self.proxy.endFilterChange(QtCore.QSortFilterProxyModel.Direction.Rows)
            else:  # Qt 6.8/6.9 compatibility
                self.proxy.filters = filters
                self.proxy.invalidateFilter()
            issues = list(workspace.errors)
            if self.settings_error: issues.append('Saved views unavailable: ' + self.settings_error)
            self.notice.setText(f'{self.proxy.rowCount()} shown / {len(workspace.records)} receptions — READ ONLY. '
                                'Historical/review records are not live confirmations. ' + '\n'.join(issues))
            if self.station_key:
                try:
                    ident, frequency, country, region = json.loads(self.station_key)
                    label = f'{ident} · {frequency:g} kHz · {country} {region}'
                except (ValueError, TypeError):
                    label = 'unresolved record only'
                self.context.setText(f'Station history: {label} — exact ID, nominal frequency and country/region')
            else:
                self.context.setText('Combined view only — no records merged into the live logbook')
            if self.proxy.rowCount() and not self.table.currentIndex().isValid(): self.table.selectRow(0)
            self.selection_changed()

        def selected(self):
            index = self.table.currentIndex()
            if not index.isValid(): return None
            source = self.proxy.mapToSource(index)
            return self.model.records[source.row()]

        def selection_changed(self, *_):
            record = self.selected()
            self.details.setPlainText(reception_summary(record) if record else 'No reception selected.')
            self.raw_details.setPlainText(record.details() if record else '')

        def reload(self):
            selected = self.selected()
            workspace.reload()
            self.model.refresh()
            for combo, values in ((self.source, {r.source for r in workspace.records}),
                                  (self.status, {r.status for r in workspace.records}),
                                  (self.event, {r.event for r in workspace.records if r.event})):
                previous = combo.currentData()
                combo.blockSignals(True)
                combo.clear()
                combo.addItem('All', '')
                for value in sorted(values): combo.addItem(value, value)
                self.set_combo(combo, previous or '')
                combo.blockSignals(False)
            self.apply_filters()
            if selected:
                for row in range(self.proxy.rowCount()):
                    if self.proxy.index(row, 0).data(Qt.ItemDataRole.UserRole) == selected.id:
                        self.table.selectRow(row)
                        break

        @staticmethod
        def set_combo(combo, value):
            index = combo.findData(value)
            if index < 0:
                combo.addItem(value + ' (not present)', value)
                index = combo.count() - 1
            combo.setCurrentIndex(index)

        def restore_filter(self, fields):
            filters = BrowserFilter(**fields)
            widgets = (self.search, self.source, self.status, self.event, self.date_from,
                       self.date_to, self.minimum, self.maximum, self.review)
            for widget in widgets: widget.blockSignals(True)
            self.search.setText(filters.search)
            for combo, value in ((self.source, filters.source), (self.status, filters.status), (self.event, filters.event)):
                self.set_combo(combo, value)
            self.date_from.setText(filters.date_from)
            self.date_to.setText(filters.date_to)
            self.minimum.setValue(filters.minimum_khz or 0)
            self.maximum.setValue(filters.maximum_khz or 0)
            self.review.setChecked(filters.review_only)
            self.station_key = filters.station_key
            for widget in widgets: widget.blockSignals(False)
            self.apply_filters()

        def clear_filters(self):
            self.station_key = ''
            self.restore_filter({})

        def show_history(self):
            record = self.selected()
            if not record: return
            if not self.station_key: self.history_previous = asdict(self.filter_state())
            self.restore_filter(dict(station_key=record.station_key))

        def back(self):
            previous = self.history_previous or {}
            self.history_previous = None
            self.restore_filter(previous)

        def choose_view(self, *_):
            name = self.view.currentText()
            builtins = {'All receptions': {}, 'Needs review': {'review_only': True}, 'Tentative': {'status': 'tentative'}}
            self.restore_filter(builtins.get(name, self.custom_views.get(name, {})))

        def save_view(self):
            if settings_path is None or self.settings_error:
                QtWidgets.QMessageBox.warning(self, 'Cannot save view', 'Settings are disabled or unreadable; source data is unchanged.')
                return
            name, okay = QtWidgets.QInputDialog.getText(self, 'Save current view', 'View name:')
            name = name.strip()
            if not okay or not name: return
            if name in ('All receptions', 'Needs review', 'Tentative'):
                QtWidgets.QMessageBox.warning(self, 'Reserved name', 'Choose a different view name.')
                return
            updated = self.custom_views | {name: asdict(self.proxy.filters)}
            try: save_views(settings_path, updated)
            except (OSError, ValueError) as exc:
                QtWidgets.QMessageBox.warning(self, 'View not saved', str(exc))
                return
            self.custom_views = updated
            if self.view.findText(name) < 0: self.view.addItem(name)
            self.view.setCurrentText(name)

        def add_source(self):
            filename, _ = QtWidgets.QFileDialog.getOpenFileName(self, 'Open read-only log source', '',
                'Log sources (*.sqlite *.json);;All files (*)')
            if filename:
                path = Path(filename)
                workspace.sources.append(StagedLogSource(path) if path.suffix.lower() == '.json' else NativeLogSource(path))
                self.reload()

    return Window()


def main(argv=None):
    parser = argparse.ArgumentParser(description='Standalone read-only reception browser; no radio connection or import')
    parser.add_argument('--logbook', type=Path, action='append', help='native SQLite source; repeatable')
    parser.add_argument('--stage', type=Path, action='append', help='WWSU review JSON; repeatable')
    parser.add_argument('--native-only', action='store_true', help='omit the default data/wwsu-stage.json')
    parser.add_argument('--settings', type=Path, default=Path.home() / '.config/kiwi-client/log-browser.json')
    parser.add_argument('--dry-run', action='store_true', help='read and summarize sources without starting Qt')
    args = parser.parse_args(argv)
    native_paths = args.logbook if args.logbook is not None else ([Path('receptions.sqlite')] if Path('receptions.sqlite').is_file() else [])
    sources = [NativeLogSource(path) for path in native_paths]
    stages = args.stage if args.stage is not None else ([] if args.native_only or not Path('data/wwsu-stage.json').is_file()
                                                     else [Path('data/wwsu-stage.json')])
    sources.extend(StagedLogSource(path) for path in stages)
    workspace = LogWorkspace(sources)
    if args.dry_run:
        from collections import Counter
        workspace.reload()
        print(json.dumps(dict(records=len(workspace.records), sources=Counter(r.source for r in workspace.records),
                              statuses=Counter(r.status for r in workspace.records), errors=workspace.errors), indent=2))
        return 1 if workspace.errors else 0
    try:
        from PySide6.QtWidgets import QApplication
    except ImportError:
        parser.error('install the gui-pyside extra (PySide6-Essentials) to use the desktop browser')
    app = QApplication.instance() or QApplication([])
    window = create_window(workspace, settings_path=args.settings.expanduser())
    window.show()
    return app.exec()


if __name__ == '__main__':
    raise SystemExit(main())
