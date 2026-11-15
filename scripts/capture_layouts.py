"""Generate Qt-rendered layout checks. Run with QT_SCALE_FACTOR set externally."""
import os
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from PySide6.QtCore import QSettings
from PySide6.QtWidgets import QApplication
from keywave.ui.window import MainWindow
from keywave.storage import History

app = QApplication([])
app.setStyle('Fusion')
directory = Path('artifacts/layouts')
directory.mkdir(parents=True, exist_ok=True)
settings = QSettings(str(directory.resolve()/'settings.ini'), QSettings.IniFormat)
settings.clear()
settings.setValue('reduced', True)
window = MainWindow(settings, History(directory/'history.json'))
scale = os.environ.get('QT_SCALE_FACTOR','1')
window.show()
for language in (0,1):
    window.language.setCurrentIndex(language)
    for width, height in ((960,640),(1200,780)):
        window.resize(width,height)
        for page in (0,1,2,4):
            window.navigate(page)
            for _ in range(4):
                app.processEvents()
            window.grab().save(str(directory/f'{scale}-{language}-{width}-{page}.png'))
window.close()
