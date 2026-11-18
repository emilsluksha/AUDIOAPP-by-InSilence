# Standalone windowed executable; runtime resources unpack under sys._MEIPASS.
from PyInstaller.utils.hooks import collect_all, collect_data_files, copy_metadata
from pathlib import Path
import ssl

datas = [('localization', 'localization'), ('assets', 'assets'),
         ('licenses', 'licenses'), ('runtime', 'runtime'), ('THIRD_PARTY_NOTICES.md', '.'), ('LICENSE', '.')]
binaries = []
# The bundled development Python loads this trust-policy resource when creating
# any SSLContext. Preserve it when present; stock Python does not need it.
ssl_policy = Path(ssl.__file__).with_name('codex-rejected-cas.pem')
if ssl_policy.is_file():
    datas.append((str(ssl_policy), '.'))
hiddenimports = ['scipy.special._ufuncs', 'scipy.signal', 'scipy.ndimage', 'sklearn.utils._cython_blas']
for package in ('librosa', 'lazy_loader', 'imageio_ffmpeg', 'pyloudnorm', 'yt_dlp', 'yt_dlp_ejs'):
    d, b, h = collect_all(package)
    datas += d
    binaries += b
    hiddenimports += h
datas += collect_data_files('librosa', includes=['**/*.pyi'])
for package in ('librosa', 'soundfile', 'numpy', 'scipy', 'numba', 'imageio-ffmpeg'):
    datas += copy_metadata(package)
a = Analysis(['main.py'], pathex=[], binaries=binaries, datas=datas,
             hiddenimports=hiddenimports, hookspath=[], runtime_hooks=[],
             excludes=['tkinter', 'matplotlib', 'PyQt5', 'PyQt6', 'PySide2', 'IPython', 'pytest'],
             noarchive=False)
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, a.binaries, a.datas, [], name='KEYWAVE', debug=False,
          bootloader_ignore_signals=False, strip=False, upx=False, console=False,
          icon='assets/keywave.ico')
