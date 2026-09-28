import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

from kiwi_client.log_browser import create_window
from kiwi_client.log_browser_data import LogWorkspace, StagedLogSource


@pytest.mark.parametrize('control', ['search', 'table', 'details', 'raw_details', 'button'])
def test_quit_closes_normally_without_writing_sources(tmp_path, monkeypatch, control):
    monkeypatch.setenv('QT_QPA_PLATFORM', 'offscreen')
    pytest.importorskip('PySide6')
    from PySide6 import QtCore, QtTest, QtWidgets
    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    stage = tmp_path / 'stage.json'
    stage.write_text(json.dumps({'schema': 1, 'kind': 'wwsu-review-stage', 'records': []}))
    preferences = tmp_path / 'views.json'
    preferences.write_text(json.dumps({'schema': 1, 'views': {}}))
    before = [path.read_bytes() for path in (stage, preferences)]
    window = create_window(LogWorkspace([StagedLogSource(stage)]), settings_path=preferences)
    window.show()
    window.activateWindow()
    app.processEvents()
    try:
        assert window.isVisible()
        if control == 'button':
            button = window.findChild(QtWidgets.QToolButton, 'quitButton')
            assert button is not None and button.isVisible()
            assert 'Quit' in button.text()
            QtTest.QTest.mouseClick(button, QtCore.Qt.MouseButton.LeftButton)
        else:
            target = getattr(window, control)
            if control in ('details', 'raw_details'):
                window.findChild(QtWidgets.QTabWidget).setCurrentWidget(target)
            target.setFocus()
            app.processEvents()
            QtTest.QTest.keyClick(target, QtCore.Qt.Key.Key_Q, QtCore.Qt.KeyboardModifier.ControlModifier)
        app.processEvents()
        assert not window.isVisible()
        assert before == [path.read_bytes() for path in (stage, preferences)]
    finally:
        window.close()


def test_quit_returns_from_application_event_loop(monkeypatch):
    pytest.importorskip('PySide6')
    monkeypatch.setenv('QT_QPA_PLATFORM', 'offscreen')
    env = dict(os.environ, PYTHONPATH=str(Path(__file__).parents[2] / 'src'))
    script = '''
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication
from kiwi_client.log_browser import create_window
from kiwi_client.log_browser_data import LogWorkspace
app = QApplication([])
window = create_window(LogWorkspace([]))
window.show()
QTimer.singleShot(0, window.quit_action.trigger)
assert app.exec() == 0
assert not window.isVisible()
print('normal exit')
'''
    result = subprocess.run([sys.executable, '-c', script], env=env,
                            capture_output=True, text=True, timeout=10, check=True)
    assert result.stdout.strip() == 'normal exit'
