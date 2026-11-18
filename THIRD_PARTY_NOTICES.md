# Third-party software

KEYWAVE's original source is provided under MIT. The application logo was supplied
by the project owner and prepared with transparent outer background using the
built-in image tool; it is not part of any third-party dependency.
Dependencies retain their own licenses. License texts collected from the exact
installed wheels are in `licenses/` and are included in the portable build.

YouTube downloads use yt-dlp (Unlicense), yt-dlp-ejs (Unlicense), and a bundled
official Node.js runtime (MIT and included third-party notices in Node-LICENSE.txt).
Optional yt-dlp dependencies retain the licenses collected in `licenses/`.

- Python: PSF license — https://www.python.org/downloads/source/
- PySide6 / Qt 6.8.3 / Shiboken: LGPL v3 / GPL options, dynamically linked.
  https://download.qt.io/official_releases/QtForPython/pyside6/
  https://download.qt.io/archive/qt/6.8/6.8.3/single/
- pyqtgraph: MIT — https://github.com/pyqtgraph/pyqtgraph
- NumPy, SciPy, librosa, scikit-learn, Numba: BSD-family licenses.
  https://github.com/numpy/numpy · https://github.com/scipy/scipy
  https://github.com/librosa/librosa · https://github.com/scikit-learn/scikit-learn
  https://github.com/numba/numba
- llvmlite / LLVM: BSD / Apache 2.0 with LLVM exceptions.
  https://github.com/numba/llvmlite
- SoundFile: BSD; libsndfile: LGPL 2.1 — https://github.com/bastibe/python-soundfile
- pyloudnorm: MIT — https://github.com/csteinmetz1/pyloudnorm
- imageio-ffmpeg: BSD wrapper. Bundled FFmpeg is a separate executable;
  its own build configuration determines the applicable GPL/LGPL license.
  https://github.com/imageio/imageio-ffmpeg
- PyInstaller: GPL with bootloader distribution exception.
  https://pyinstaller.org/en/stable/license.html

The onefile package extracts dynamically linked Qt and other libraries at runtime.
The application source, dependency manifests, KEYWAVE.spec and build.bat are
provided to rebuild the executable with compatible modified libraries.
Users may replace or relink LGPL libraries with compatible modified versions,
and may reverse engineer the application to debug those modifications.
No KEYWAVE term restricts those rights. A compatible replacement FFmpeg binary
can be selected using `IMAGEIO_FFMPEG_EXE`.

Before redistributing the portable application to third parties, supply the
corresponding source and build information required by the bundled codec's
license alongside the binaries. A link alone is not a substitute for applicable
GPL source-distribution obligations. The repository workflow creates a build
artifact, not a tagged public release.
