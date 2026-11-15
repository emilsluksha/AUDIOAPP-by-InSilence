from __future__ import annotations
import logging
from logging.handlers import RotatingFileHandler
import os
from pathlib import Path
import sys

# Numba needs a writable cache when frozen in Program Files.
cache = Path(os.environ.get('LOCALAPPDATA', Path.home())) / 'KEYWAVE' / 'cache'
cache.mkdir(parents=True, exist_ok=True)
os.environ.setdefault('NUMBA_CACHE_DIR', str(cache))
os.environ.setdefault('QT_API', 'pyside6')


def main():
    from PySide6.QtWidgets import QApplication
    from PySide6.QtCore import QTimer
    from keywave.core import data_dir
    handler = RotatingFileHandler(data_dir()/'keywave.log', maxBytes=2_000_000, backupCount=2, encoding='utf-8')
    logging.basicConfig(level=logging.INFO, handlers=[handler], format='%(asctime)s %(levelname)s %(message)s')
    app = QApplication(sys.argv)
    app.setApplicationName('KEYWAVE')
    app.setOrganizationName('KEYWAVE')
    app.setStyle('Fusion')
    from keywave.ui.window import MainWindow
    if '--smoke-test' in sys.argv:
        from PySide6.QtCore import QSettings
        from keywave.storage import History
        smoke_dir = Path(os.environ.get('KEYWAVE_SMOKE_DIR', 'artifacts')).resolve()
        smoke_dir.mkdir(parents=True, exist_ok=True)
        smoke_settings = QSettings(str(smoke_dir/'smoke-settings.ini'), QSettings.IniFormat)
        smoke_settings.clear()
        window = MainWindow(smoke_settings, History(smoke_dir/'smoke-history.json'))
    else:
        window = MainWindow()
    window.show()
    if '--smoke-test' in sys.argv:
        from keywave.smoke import run_smoke
        QTimer.singleShot(200, lambda: run_smoke(app, window))
    elif len(sys.argv) > 1 and Path(sys.argv[1]).is_file():
        QTimer.singleShot(200, lambda: window.load_file(sys.argv[1]))
    return app.exec()


if __name__ == '__main__':
    sys.exit(main())
