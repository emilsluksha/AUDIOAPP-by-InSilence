import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
from PySide6.QtCore import QSettings
from PySide6.QtWidgets import QApplication
from keywave.storage import History
from keywave.ui.window import MainWindow
from keywave.ui.widgets import DropZone


def test_navigation_translation_preferences(tmp_path):
    app = QApplication.instance() or QApplication([])
    settings = QSettings(str(tmp_path/'settings.ini'), QSettings.IniFormat)
    window = MainWindow(settings, History(tmp_path/'history.json'))
    window.show()
    for i in range(7):
        window.nav[i].click()
        assert window.stack.currentIndex() == i
    window.language.setCurrentIndex(1)
    window.navigate(4)
    assert window.heading.text() == 'Настройки'
    vocal = window.vocal_page
    vocal.key.setCurrentIndex(8)
    assert vocal.key.currentText() == 'G#'
    vocal.scale.setCurrentIndex(1)
    assert vocal.scale.currentData() == 'major'
    vocal.bpm.setValue(175)
    assert vocal.bpm.value() == 175
    vocal.strength.setValue(83)
    assert vocal.strength_value.text() == '83%'
    window.youtube_mode.setCurrentText('MP4')
    assert window.youtube_quality.count() == 5
    assert window.youtube_quality.itemData(4) == 2160
    window.reduced.setChecked(True)
    settings.sync()
    restored = QSettings(str(tmp_path/'settings.ini'), QSettings.IniFormat)
    assert restored.value('language') == 'ru'
    assert restored.value('reduced',type=bool)
    assert all(window.tr(key) != key for _,key in window.bindings if key not in ('WAV','MP3','FLAC'))
    window.close()
    app.processEvents()


def test_drop_accepts_local_audio(tmp_path):
    from PySide6.QtCore import QMimeData, QUrl, QPointF, Qt
    from PySide6.QtGui import QDropEvent
    app = QApplication.instance() or QApplication([])
    drop = DropZone()
    received = []
    drop.dropped.connect(received.append)
    mime = QMimeData()
    mime.setUrls([QUrl.fromLocalFile(str(tmp_path/'audio.wav'))])
    event = QDropEvent(QPointF(10,10), Qt.CopyAction, mime, Qt.LeftButton, Qt.NoModifier)
    drop.dropEvent(event)
    assert received == [str(tmp_path/'audio.wav').replace('\\','/')]
