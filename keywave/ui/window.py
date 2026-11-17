from __future__ import annotations

import csv
import json
import logging
import os
from pathlib import Path
import tempfile

import numpy as np
import pyqtgraph as pg
import soundfile as sf
from PySide6.QtCore import Qt, QSettings, QUrl, QTimer, QPropertyAnimation, QEasingCurve, QEvent
from PySide6.QtGui import QIcon, QPixmap, QDesktopServices
from PySide6.QtMultimedia import QAudioOutput, QMediaPlayer, QMediaDevices
from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, QFrame, QLabel, QVBoxLayout, QHBoxLayout,
    QGridLayout, QStackedWidget, QScrollArea, QComboBox, QCheckBox, QSlider, QProgressBar,
    QFileDialog, QMessageBox, QListWidget, QDoubleSpinBox, QFormLayout, QDialog,
    QDialogButtonBox, QGraphicsOpacityEffect, QLineEdit)

from ..core import Audio, resource, atomic_json
from ..audio import decode, export_audio, waveform
from ..analysis import analyze, NOTES
from ..mastering import master, MasterSettings, PRESETS
from ..storage import History, Translator
from .widgets import Button, DropZone, Card, Worker
from .style import STYLE

pg.setConfigOptions(antialias=True, background='#F7FBFF', foreground='#62809C')
PAGE_KEYS = ('dashboard', 'analyzer', 'mastering', 'history', 'settings', 'youtube', 'vocal_studio')


class MainWindow(QMainWindow):
    def __init__(self, settings: QSettings | None = None, history: History | None = None):
        super().__init__()
        self.settings = settings or QSettings('KEYWAVE', 'KEYWAVE')
        self.tr = Translator(self.settings.value('language', 'en'))
        self.history = history or History()
        self.audio: Audio | None = None
        self.mastered: Audio | None = None
        self.result = None
        self.master_metrics = None
        self.master_ceiling = -1.
        self.worker = None
        self.busy = False
        self.current_stage = 'ready'
        self.current_notice = None
        self.bindings = []
        self.buttons = []
        self.temp = tempfile.TemporaryDirectory(prefix='keywave-player-')
        self.original_media = ''
        self.master_media = ''
        self.media_kind = 'original'
        self.pending_seek = None
        self.output = QAudioOutput(self)
        self.player = QMediaPlayer(self)
        self.player.setAudioOutput(self.output)
        self.player.positionChanged.connect(self.position_changed)
        self.player.mediaStatusChanged.connect(self.media_loaded)
        self.player.errorOccurred.connect(lambda *_: self.notify('playback_error'))
        self.setWindowTitle('KEYWAVE')
        self.setWindowIcon(QIcon(str(resource('assets/keywave.ico'))))
        self.resize(1200, 780)
        self.setMinimumSize(960, 640)
        self.setStyleSheet(STYLE)
        self.build()
        self.retranslate()
        self.apply_preferences()
        self.refresh_history()
        self.install_audio_drop()

    AUDIO_SUFFIXES = frozenset({
        '.wav', '.mp3', '.flac', '.ogg', '.m4a', '.aac', '.aiff',
        '.aif', '.opus', '.wma'
    })

    @classmethod
    def audio_drop_path(cls, mime):
        """Accept only a single local audio file; never arbitrary URLs or folders."""
        if not mime.hasUrls() or len(mime.urls()) != 1:
            return None
        url = mime.urls()[0]
        if not url.isLocalFile():
            return None
        path = Path(url.toLocalFile())
        return str(path) if path.suffix.lower() in cls.AUDIO_SUFFIXES and path.is_file() else None

    def install_audio_drop(self):
        """One unobtrusive drop target follows the pointer across every page."""
        self.drop_overlay = QFrame(self.centralWidget())
        self.drop_overlay.setObjectName('glassOverlay')
        self.drop_overlay.setAttribute(Qt.WA_TransparentForMouseEvents)
        layout = QVBoxLayout(self.drop_overlay)
        layout.setAlignment(Qt.AlignCenter)
        layout.setSpacing(12)
        glyph = QLabel('♫')
        glyph.setObjectName('overlaySymbol')
        glyph.setAlignment(Qt.AlignCenter)
        self.drop_title = QLabel()
        self.drop_title.setObjectName('overlayTitle')
        self.drop_title.setAlignment(Qt.AlignCenter)
        self.drop_hint = QLabel()
        self.drop_hint.setObjectName('overlaySubtitle')
        self.drop_hint.setAlignment(Qt.AlignCenter)
        for item in (glyph, self.drop_title, self.drop_hint):
            layout.addWidget(item)
        self.translate_drop_overlay()
        self.drop_overlay.hide()
        QApplication.instance().installEventFilter(self)

    def translate_drop_overlay(self):
        russian = self.tr.language == 'ru'
        self.drop_title.setText('Добавьте свой трек' if russian else 'Drop your music here')
        self.drop_hint.setText(
            'Перетащите аудиофайл в KEYWAVE · MP3, WAV, FLAC и другие'
            if russian else 'Drop an audio file into KEYWAVE · MP3, WAV, FLAC and more'
        )

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if hasattr(self, 'drop_overlay'):
            self.drop_overlay.setGeometry(self.centralWidget().rect().adjusted(14, 14, -14, -14))

    def eventFilter(self, target, event):
        kind = event.type()
        if kind not in (QEvent.DragEnter, QEvent.DragMove, QEvent.DragLeave, QEvent.Drop):
            return super().eventFilter(target, event)
        if not isinstance(target, QWidget) or target.window() is not self:
            return super().eventFilter(target, event)
        if kind == QEvent.DragLeave:
            # Moving between child widgets must not remove the app-wide overlay.
            if target is self or target is self.centralWidget():
                self.drop_overlay.hide()
            return super().eventFilter(target, event)
        path = self.audio_drop_path(event.mimeData())
        if not path:
            return super().eventFilter(target, event)
        event.acceptProposedAction()
        if kind == QEvent.Drop:
            self.drop_overlay.hide()
            if self.busy:
                self.notify('busy')
            elif self.stack.currentIndex() == 6:
                self.vocal_page.load(path)
            else:
                self.load_file(path)
            return True
        self.drop_overlay.setGeometry(self.centralWidget().rect().adjusted(14, 14, -14, -14))
        self.drop_overlay.show()
        self.drop_overlay.raise_()
        return True

    def closeEvent(self, event):
        QApplication.instance().removeEventFilter(self)
        super().closeEvent(event)

    def label(self, key, style=None):
        label = QLabel()
        if style:
            label.setObjectName(style)
        if style in ('hero', 'muted'):
            label.setWordWrap(True)
        self.bindings.append((label.setText, key))
        return label

    def button(self, key, callback, primary=False):
        button = Button(primary=primary)
        self.bindings.append((button.setText, key))
        button.clicked.connect(callback)
        self.buttons.append(button)
        return button

    def build(self):
        root = QWidget()
        outer = QHBoxLayout(root)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        self.setCentralWidget(root)
        sidebar = QFrame()
        sidebar.setObjectName('sidebar')
        sidebar.setFixedWidth(214)
        nav = QVBoxLayout(sidebar)
        nav.setContentsMargins(16, 20, 16, 16)
        nav.setSpacing(6)
        logo = QLabel()
        logo.setPixmap(QPixmap(str(resource('assets/keywave.png'))).scaled(52, 52, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        nav.addWidget(logo)
        brand = QLabel('KEYWAVE')
        brand.setObjectName('brand')
        nav.addWidget(brand)
        nav.addWidget(self.label('tagline', 'muted'))
        nav.addSpacing(16)
        self.nav = []
        for index, key in enumerate(PAGE_KEYS):
            button = self.button(key, lambda checked=False, i=index: self.navigate(i))
            button.setCheckable(True)
            button.setMinimumHeight(38)
            nav.addWidget(button)
            self.nav.append(button)
        nav.addStretch()
        nav.addWidget(self.label('local_processing', 'muted'))
        nav.addWidget(QLabel('KEYWAVE  1.0.0'))
        outer.addWidget(sidebar)
        content = QWidget()
        body = QVBoxLayout(content)
        body.setContentsMargins(30, 24, 30, 19)
        body.setSpacing(14)
        header = QHBoxLayout()
        self.heading = QLabel()
        self.heading.setObjectName('heading')
        header.addWidget(self.heading)
        header.addStretch()
        self.status = self.label('ready', 'muted')
        header.addWidget(self.status)
        self.language = QComboBox()
        self.language.addItems(['EN', 'RU'])
        self.language.setCurrentIndex(1 if self.tr.language == 'ru' else 0)
        self.language.currentIndexChanged.connect(self.change_language)
        header.addWidget(self.language)
        header.addWidget(self.button('settings', lambda: self.navigate(4)))
        body.addLayout(header)
        self.stack = QStackedWidget()
        self.pages = []
        for _ in PAGE_KEYS:
            scroll = QScrollArea()
            scroll.setWidgetResizable(True)
            page = QWidget()
            layout = QVBoxLayout(page)
            layout.setContentsMargins(0, 0, 8, 4)
            layout.setSpacing(16)
            scroll.setWidget(page)
            self.stack.addWidget(scroll)
            self.pages.append(layout)
        self.build_dashboard()
        self.build_analyzer()
        self.build_mastering()
        self.build_history()
        self.build_settings()
        self.build_youtube()
        from .vocal_page import VocalPage
        self.vocal_page = VocalPage(self)
        self.pages[6].addWidget(self.vocal_page)
        body.addWidget(self.stack, 1)
        self.notice = QLabel()
        self.notice.setObjectName('muted')
        self.notice.setWordWrap(True)
        self.notice.hide()
        self.notice_effect = QGraphicsOpacityEffect(self.notice)
        self.notice.setGraphicsEffect(self.notice_effect)
        self.notice_animation = QPropertyAnimation(self.notice_effect, b'opacity', self)
        body.addWidget(self.notice)
        progress_row = QHBoxLayout()
        self.progressbar = QProgressBar()
        self.progressbar.setRange(0, 100)
        self.progressbar.setTextVisible(False)
        self.progressbar.setFixedHeight(7)
        progress_row.addWidget(self.progressbar)
        self.cancel_button = self.button('cancel', self.cancel)
        self.cancel_button.hide()
        progress_row.addWidget(self.cancel_button)
        body.addLayout(progress_row)
        self.build_player(body)
        outer.addWidget(content, 1)
        self.nav[0].setChecked(True)
        root.setAcceptDrops(True)
        self.setAcceptDrops(True)
        self.fade_effect = QGraphicsOpacityEffect(self.stack)
        self.stack.setGraphicsEffect(self.fade_effect)
        self.fade = QPropertyAnimation(self.fade_effect, b'opacity', self)
        self.fade.setEasingCurve(QEasingCurve.OutCubic)
        self.progress_anim = QPropertyAnimation(self.progressbar, b'value', self)
        self.pulse = QPropertyAnimation(self.cancel_button, b'hover', self)
        self.pulse.setStartValue(0.)
        self.pulse.setKeyValueAt(.5, 1.)
        self.pulse.setEndValue(0.)
        self.pulse.setDuration(1400)
        self.pulse.setLoopCount(-1)

    def build_dashboard(self):
        page = self.pages[0]
        page.addWidget(self.label('welcome', 'hero'))
        page.addWidget(self.label('welcome_sub', 'muted'))
        self.dropzone = DropZone()
        self.bindings.extend([(self.dropzone.title.setText, 'drop'), (self.dropzone.subtitle.setText, 'formats'), (self.dropzone.button.setText, 'browse')])
        self.dropzone.browse.connect(self.browse)
        self.dropzone.dropped.connect(self.load_file)
        page.addWidget(self.dropzone)
        self.file_info = QLabel()
        self.file_info.setWordWrap(True)
        self.file_info.setTextInteractionFlags(Qt.TextSelectableByMouse)
        page.addWidget(self.file_info)
        actions = QHBoxLayout()
        actions.addWidget(self.button('analyze', self.start_analysis, True))
        actions.addWidget(self.button('open_mastering', lambda: self.navigate(2)))
        page.addLayout(actions)
        page.addWidget(self.label('recent', 'muted'))
        self.recent = QListWidget()
        self.recent.setMinimumHeight(100)
        self.recent.itemDoubleClicked.connect(lambda item: self.load_file(item.data(Qt.UserRole)))
        page.addWidget(self.recent)
        page.addStretch()

    def plot(self, height=190):
        plot = pg.PlotWidget()
        plot.setMinimumHeight(height)
        plot.showGrid(x=True, y=True, alpha=.1)
        plot.setMenuEnabled(False)
        return plot

    def build_analyzer(self):
        page = self.pages[1]
        row = QHBoxLayout()
        row.addWidget(self.button('browse', self.browse))
        row.addWidget(self.button('analyze', self.start_analysis, True))
        row.addWidget(self.button('analyze_selection', lambda: self.start_analysis(True)))
        row.addWidget(self.button('export_report', self.export_report))
        page.addLayout(row)
        grid = QGridLayout()
        self.cards = []
        for i, key in enumerate(('musical_key', 'tempo', 'frequency', 'confidence')):
            card = Card()
            self.bindings.append((card.title.setText, key))
            self.cards.append(card)
            grid.addWidget(card, i//2, i%2)
        page.addLayout(grid)
        self.warnings = QLabel()
        self.warnings.setWordWrap(True)
        self.warnings.setObjectName('muted')
        page.addWidget(self.warnings)
        page.addWidget(self.label('wave_help', 'muted'))
        self.wave = self.plot(170)
        self.wave.setMaximumHeight(230)
        self.wave_low = self.wave.plot(pen=pg.mkPen('#8B5CF6', width=1))
        self.wave_high = self.wave.plot(pen=pg.mkPen('#EC4899', width=1))
        self.wave.addItem(pg.FillBetweenItem(self.wave_low, self.wave_high, brush=pg.mkBrush(139, 92, 246, 90)))
        self.region = pg.LinearRegionItem([0, 1], brush=pg.mkBrush(236, 72, 153, 25))
        self.wave.addItem(self.region)
        self.playhead = pg.InfiniteLine(0, pen=pg.mkPen('#F8F5FF', width=2))
        self.wave.addItem(self.playhead)
        self.wave.scene().sigMouseClicked.connect(self.wave_click)
        page.addWidget(self.wave)
        self.spectrum = self.plot()
        self.spectrum.setLogMode(x=True)
        self.spectrum_curve = self.spectrum.plot(pen=pg.mkPen('#F472B6', width=1.5), fillLevel=-160, brush=pg.mkBrush(139, 92, 246, 35))
        page.addWidget(self.spectrum)
        self.spectrogram = self.plot(230)
        self.spec_image = pg.ImageItem(axisOrder='row-major')
        cmap = pg.ColorMap([0, .4, .75, 1], ['#0D0A14', '#4C2380', '#A855F7', '#F9A8D4'])
        self.spec_image.setLookupTable(cmap.getLookupTable())
        self.spectrogram.addItem(self.spec_image)
        page.addWidget(self.spectrogram)
        self.chroma_plot = self.plot(160)
        self.chroma_plot.getAxis('bottom').setTicks([list(enumerate(NOTES))])
        self.chroma_bars = pg.BarGraphItem(x=np.arange(12), height=np.zeros(12), width=.65, brush='#A855F7')
        self.chroma_plot.addItem(self.chroma_bars)
        page.addWidget(self.chroma_plot)
        self.candidate_label = QLabel()
        self.candidate_label.setWordWrap(True)
        page.addWidget(self.candidate_label)
        self.peak_label = QLabel()
        self.peak_label.setWordWrap(True)
        page.addWidget(self.peak_label)

    def build_mastering(self):
        page = self.pages[2]
        page.addWidget(self.label('master_intro', 'muted'))
        row = QHBoxLayout()
        self.presets = QComboBox()
        for preset in PRESETS:
            self.presets.addItem('', preset)
        self.presets.currentIndexChanged.connect(self.preset_changed)
        row.addWidget(self.presets, 1)
        row.addWidget(self.button('start_mastering', self.start_mastering, True))
        row.addWidget(self.button('export_master', self.export_master))
        page.addLayout(row)
        self.controls = {}
        grid = QGridLayout()
        for index, (key, minimum, maximum, value, suffix) in enumerate([
            ('intensity', 0, 100, 60, '%'), ('target', -24, -6, -14, ' LUFS'),
            ('width', 0, 150, 100, '%'), ('eq', 0, 100, 50, '%'),
            ('compression', 0, 100, 50, '%'), ('ceiling', -3, -.1, -1, ' dBTP')]):
            card = QFrame()
            card.setObjectName('card')
            layout = QVBoxLayout(card)
            layout.addWidget(self.label(key, 'muted'))
            spin = QDoubleSpinBox()
            spin.setRange(minimum, maximum)
            spin.setDecimals(1 if key in ('target', 'ceiling') else 0)
            spin.setSingleStep(.1 if key == 'ceiling' else 1)
            spin.setValue(value)
            spin.setSuffix(suffix)
            layout.addWidget(spin)
            self.controls[key] = spin
            grid.addWidget(card, index//3, index%3)
        page.addLayout(grid)
        self.advanced_button = self.button('advanced', self.toggle_advanced)
        page.addWidget(self.advanced_button)
        self.advanced = self.label('dsp_explanation', 'muted')
        self.advanced.setWordWrap(True)
        self.advanced.setMaximumHeight(0)
        page.addWidget(self.advanced)
        self.advanced_animation = QPropertyAnimation(self.advanced, b'maximumHeight', self)
        self.advanced_animation.setDuration(220)
        compare = QHBoxLayout()
        compare.addWidget(self.button('original', lambda: self.switch_media('original')))
        compare.addWidget(self.button('mastered', lambda: self.switch_media('mastered')))
        self.match = QCheckBox()
        self.bindings.append((self.match.setText, 'loudness_match'))
        self.match.setChecked(True)
        self.match.toggled.connect(self.update_volume)
        compare.addWidget(self.match)
        page.addLayout(compare)
        self.compare_label = QLabel('—')
        self.compare_label.setWordWrap(True)
        page.addWidget(self.compare_label)
        self.compare_plot = self.plot(220)
        self.before_curve = self.compare_plot.plot(pen=pg.mkPen('#8B5CF6', width=1))
        self.after_curve = self.compare_plot.plot(pen=pg.mkPen('#F472B6', width=1))
        page.addWidget(self.compare_plot)
        page.addWidget(self.label('master_note', 'muted'))
        page.addStretch()

    def build_history(self):
        page = self.pages[3]
        page.addWidget(self.label('history_hint', 'muted'))
        self.history_list = QListWidget()
        self.history_list.itemDoubleClicked.connect(lambda _: self.show_history())
        page.addWidget(self.history_list, 1)
        row = QHBoxLayout()
        for key, callback in [('view_result', self.show_history), ('reanalyze', self.reanalyze_history),
                              ('delete', self.delete_history), ('clear_history', self.clear_history)]:
            row.addWidget(self.button(key, callback))
        page.addLayout(row)

    def build_settings(self):
        page = self.pages[4]
        form = QFormLayout()
        form.setSpacing(16)
        self.pref_widgets = {}
        options = {'theme': [('violet', 'violet'), ('contrast', 'contrast')],
                   'animation': [('full', 'full_motion'), ('minimal', 'minimal_motion')],
                   'quality': [('full', 'full_analysis'), ('quick', 'quick_analysis')],
                   'performance': [('normal', 'normal'), ('economy', 'economy')],
                   'export_format': [('wav', 'WAV'), ('flac', 'FLAC'), ('mp3', 'MP3')]}
        for key, choices in options.items():
            combo = QComboBox()
            for value, text in choices:
                combo.addItem(self.tr(text), value)
            value = self.settings.value(key, choices[0][0])
            combo.setCurrentIndex(max(0, combo.findData(value)))
            combo.currentIndexChanged.connect(lambda _, k=key, c=combo: self.save_preference(k, c.currentData()))
            form.addRow(self.label(key), combo)
            self.pref_widgets[key] = combo
        self.reduced = QCheckBox()
        self.reduced.setChecked(self.settings.value('reduced', False, type=bool))
        self.reduced.toggled.connect(lambda value: self.save_preference('reduced', value))
        form.addRow(self.label('reduced'), self.reduced)
        self.devices = QComboBox()
        self.devices.addItem(self.tr('system_default'), '')
        for device in QMediaDevices.audioOutputs():
            self.devices.addItem(device.description(), bytes(device.id()).hex())
        self.devices.setCurrentIndex(max(0, self.devices.findData(self.settings.value('device', ''))))
        self.devices.currentIndexChanged.connect(self.device_changed)
        form.addRow(self.label('device'), self.devices)
        folder_row = QHBoxLayout()
        self.export_folder = QLineEdit(self.settings.value('export_folder', str(Path.home() / 'Music')))
        self.export_folder.editingFinished.connect(lambda: self.save_preference('export_folder', self.export_folder.text()))
        folder_row.addWidget(self.export_folder)
        folder_row.addWidget(self.button('browse', self.choose_folder))
        form.addRow(self.label('export_folder'), folder_row)
        page.addLayout(form)
        page.addWidget(self.button('clear_history', self.clear_history))
        page.addWidget(self.button('reset_settings', self.reset_settings))
        page.addWidget(self.button('licenses', lambda: QDesktopServices.openUrl(QUrl.fromLocalFile(str(resource('THIRD_PARTY_NOTICES.md'))))))
        page.addWidget(self.label('privacy', 'muted'))
        page.addStretch()

    def build_youtube(self):
        page = self.pages[5]
        page.addWidget(self.label('youtube_intro', 'muted'))
        form = QFormLayout()
        self.youtube_link = QLineEdit()
        self.youtube_link.setPlaceholderText('https://www.youtube.com/watch?v=…')
        form.addRow(self.label('youtube_link'), self.youtube_link)
        self.youtube_link.textChanged.connect(self.clear_youtube_preview)
        preview_row = QHBoxLayout()
        self.youtube_thumbnail = QLabel()
        self.youtube_thumbnail.setFixedSize(220,124)
        self.youtube_thumbnail.setScaledContents(False)
        preview_row.addWidget(self.youtube_thumbnail)
        self.youtube_metadata = QLabel('—')
        self.youtube_metadata.setTextFormat(Qt.PlainText)
        self.youtube_metadata.setWordWrap(True)
        preview_row.addWidget(self.youtube_metadata,1)
        self.youtube_thumbnail.hide()
        self.youtube_metadata.hide()
        row = QHBoxLayout()
        self.youtube_folder = QLineEdit(self.settings.value('youtube_folder', str(Path.home()/'Music'/'KEYWAVE')))
        row.addWidget(self.youtube_folder)
        row.addWidget(self.button('youtube_folder_choose', self.choose_youtube_folder))
        form.addRow(self.label('export_folder'), row)
        self.youtube_quality = QComboBox()
        self.youtube_mode = QComboBox()
        self.youtube_mode.addItems(['MP3','MP4'])
        self.youtube_mode.currentIndexChanged.connect(self.youtube_format_changed)
        form.addRow(self.label('format'),self.youtube_mode)
        self.youtube_format_changed()
        form.addRow(self.label('youtube_quality'), self.youtube_quality)
        page.addLayout(form)
        page.addWidget(self.button('youtube_preview', self.preview_youtube))
        page.addLayout(preview_row)
        page.addWidget(self.button('youtube_download', self.start_download, True))
        self.youtube_result = QLabel()
        self.youtube_result.setWordWrap(True)
        self.youtube_result.setTextInteractionFlags(Qt.TextSelectableByMouse)
        page.addWidget(self.youtube_result)
        self.youtube_speed = QLabel('—')
        page.addWidget(self.youtube_speed)
        self.downloaded_path = None
        self.youtube_open = self.button('youtube_open', self.open_download)
        self.youtube_open.setEnabled(False)
        page.addWidget(self.youtube_open)
        page.addWidget(self.button('open_folder',self.open_download_folder))
        page.addWidget(self.label('youtube_quality_note', 'muted'))
        page.addStretch()

    def choose_youtube_folder(self):
        folder = QFileDialog.getExistingDirectory(self, self.tr('export_folder'), self.youtube_folder.text())
        if folder:
            self.youtube_folder.setText(folder)
            self.settings.setValue('youtube_folder', folder)

    def start_download(self):
        from ..downloader import download_media
        if self.busy:
            self.notify('busy')
            return
        url, folder, quality = self.youtube_link.text(), self.youtube_folder.text().strip(), self.youtube_quality.currentData()
        mode = self.youtube_mode.currentText().lower()
        if not folder:
            self.notify('write_error')
            return
        self.settings.setValue('youtube_folder', folder)
        def done(path):
            self.downloaded_path = path
            self.youtube_result.setText(path)
            self.youtube_open.setEnabled(True)
            self.notify('youtube_done')
            self.youtube_speed.setText(self.tr('youtube_done'))
        self.run_job(lambda progress: download_media(url,folder,mode,quality,progress),done,self.youtube_details,self.youtube_failed)

    def youtube_failed(self, reason):
        # Show the localized summary and the underlying yt-dlp error in the downloader.
        summary, separator, details = reason.partition(': ')
        self.youtube_result.setText(
            self.tr(summary) + ('\n\n' + details if separator else '')
        )
        self.youtube_speed.setText('—')
        self.youtube_open.setEnabled(False)

    def youtube_format_changed(self,*_):
        self.youtube_quality.clear()
        if self.youtube_mode.currentText() == 'MP3':
            for bitrate in (128,192,256,320):
                self.youtube_quality.addItem(f'{bitrate} kbps',bitrate)
            self.youtube_quality.setCurrentIndex(1)
        else:
            self.youtube_quality.addItem(self.tr('best_available'),0)
            for height in (720,1080,1440,2160):
                self.youtube_quality.addItem(f'{height}p'+(' / 4K' if height == 2160 else ''),height)

    def clear_youtube_preview(self,*_):
        if hasattr(self,'youtube_thumbnail'):
            self.youtube_thumbnail.clear()
            self.youtube_metadata.setText('—')
            self.youtube_thumbnail.hide()
            self.youtube_metadata.hide()

    def preview_youtube(self):
        from ..downloader import preview
        url = self.youtube_link.text()
        def done(info):
            if url != self.youtube_link.text():
                return
            self.youtube_details(info)
            pixmap = QPixmap()
            if info.get('thumbnail') and pixmap.loadFromData(info['thumbnail']):
                self.youtube_thumbnail.setPixmap(pixmap.scaled(220,124,Qt.KeepAspectRatio,Qt.SmoothTransformation))
                self.youtube_thumbnail.show()
        self.run_job(lambda progress:preview(url,progress),done,on_error=self.youtube_failed)

    def youtube_details(self,info):
        if 'title' in info:
            self.youtube_metadata.show()
            duration = info.get('duration')
            time = f'{int(duration)//60}:{int(duration)%60:02}' if duration else '—'
            heights = ', '.join(f'{h}p' for h in info.get('heights',[]))
            self.youtube_metadata.setText(f'{info["title"]}\n{time}\n{heights}')
        if 'speed' in info:
            speed,eta = info.get('speed'),info.get('eta')
            self.youtube_speed.setText((f'{speed/1024**2:.2f} MB/s' if speed else '—')+'  ·  '+self.tr('remaining')+': '+(f'{int(eta)//60}:{int(eta)%60:02}' if eta is not None else '—'))

    def open_download_folder(self):
        folder = Path(self.downloaded_path).parent if self.downloaded_path else Path(self.youtube_folder.text()).expanduser()
        if folder.is_dir():
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(folder.resolve())))
        else:
            self.notify('missing_file')

    def open_download(self):
        if self.downloaded_path and not self.busy:
            self.load_file(self.downloaded_path)
            self.navigate(1)

    def build_player(self, body):
        self.player_frame = QFrame()
        self.player_frame.setObjectName('card')
        layout = QVBoxLayout(self.player_frame)
        self.player_name = QLabel('—')
        self.player_name.setObjectName('muted')
        layout.addWidget(self.player_name)
        self.seek = QSlider(Qt.Horizontal)
        self.seek.setRange(0, 0)
        self.seek.sliderMoved.connect(self.player.setPosition)
        layout.addWidget(self.seek)
        row = QHBoxLayout()
        row.addWidget(self.button('play', self.play, True))
        row.addWidget(self.button('pause', self.player.pause))
        row.addWidget(self.button('stop', self.player.stop))
        self.time_label = QLabel('00:00 / 00:00')
        row.addWidget(self.time_label)
        row.addStretch()
        self.mute = QCheckBox()
        self.bindings.append((self.mute.setText, 'mute'))
        self.mute.toggled.connect(self.output.setMuted)
        row.addWidget(self.mute)
        self.volume = QSlider(Qt.Horizontal)
        self.volume.setFixedWidth(110)
        self.volume.setRange(0, 100)
        self.volume.setValue(80)
        self.volume.valueChanged.connect(self.update_volume)
        row.addWidget(self.volume)
        layout.addLayout(row)
        body.addWidget(self.player_frame)
        self.output.setVolume(.8)

    def reduced_motion(self):
        return self.settings.value('reduced', False, type=bool) or self.settings.value('animation', 'full') == 'minimal'

    def animate_page(self):
        self.fade.stop()
        self.fade.setDuration(0 if self.reduced_motion() else 230)
        self.fade.setStartValue(.35 if not self.reduced_motion() else 1.)
        self.fade.setEndValue(1.)
        self.fade.start()

    def navigate(self, index):
        self.player_frame.setVisible(index != 6)
        if index == 6:
            self.player.pause()
        elif hasattr(self, 'vocal_page'):
            self.vocal_page.player.pause()
        self.stack.setCurrentIndex(index)
        for i, button in enumerate(self.nav):
            button.setChecked(i == index)
        self.heading.setText(self.tr(PAGE_KEYS[index]))
        self.animate_page()

    def change_language(self, index):
        self.tr.language = ('en', 'ru')[index]
        self.settings.setValue('language', self.tr.language)
        self.retranslate()

    def retranslate(self):
        for setter, key in self.bindings:
            setter(self.tr(key))
        self.heading.setText(self.tr(PAGE_KEYS[self.stack.currentIndex()]))
        if hasattr(self, 'drop_overlay'):
            self.translate_drop_overlay()
        for index in range(self.presets.count()):
            self.presets.setItemText(index, self.tr(self.presets.itemData(index)))
        for key, texts in {'theme':['violet','contrast'], 'animation':['full_motion','minimal_motion'],
                           'quality':['full_analysis','quick_analysis'], 'performance':['normal','economy']}.items():
            for i, text in enumerate(texts):
                self.pref_widgets[key].setItemText(i, self.tr(text))
        self.devices.setItemText(0, self.tr('system_default'))
        self.wave.setLabel('bottom', self.tr('time'), units='s')
        self.wave.setLabel('left', self.tr('amplitude'))
        self.spectrum.setLabel('bottom', self.tr('frequency'), units='Hz')
        self.spectrum.setLabel('left', self.tr('power'), units='dB/Hz')
        self.spectrogram.setLabel('bottom', self.tr('time'), units='s')
        self.spectrogram.setLabel('left', self.tr('frequency'), units='Hz')
        self.chroma_plot.setLabel('left', self.tr('note_distribution'))
        self.compare_plot.setLabel('bottom', self.tr('time'), units='s')
        self.volume.setToolTip(self.tr('volume'))
        self.seek.setToolTip(self.tr('seek'))
        self.status.setText(self.tr(self.current_stage))
        if self.current_notice:
            self.notice.setText(self.tr(self.current_notice))
        if self.audio:
            self.player_name.setText(f'{Path(self.audio.path).name}  ·  {self.tr(self.media_kind)}')
        if self.result:
            self.display_result(self.result, animate=False)
        self.update_file_info()
        self.update_comparison()
        self.refresh_history()

        self.vocal_page.translate()
        if self.youtube_mode.currentText() == 'MP4':
            self.youtube_quality.setItemText(0,self.tr('best_available'))

    def notify(self, key):
        self.current_notice = key
        self.notice.setText(self.tr(key))
        self.notice.show()
        self.notice_animation.stop()
        self.notice_animation.setDuration(0 if self.reduced_motion() else 200)
        self.notice_animation.setStartValue(0.)
        self.notice_animation.setEndValue(1.)
        self.notice_animation.start()
        QTimer.singleShot(15000, self.notice.hide)

    def browse(self):
        path, _ = QFileDialog.getOpenFileName(self, self.tr('browse'), '', self.tr('audio_files') + ' (*.wav *.mp3 *.flac *.ogg *.m4a *.aac *.aiff *.aif *.opus *.wma)')
        if path:
            self.load_file(path)

    def run_job(self, function, callback, details=None, on_error=None):
        if self.busy:
            self.notify('busy')
            return
        self.busy = True
        self.progressbar.setValue(0)
        self.cancel_button.show()
        self.status.setText(self.tr('working'))
        if not self.reduced_motion():
            self.pulse.start()
        self.worker = Worker(function, self)
        self.worker.progress_changed.connect(self.set_progress)
        if details:
            self.worker.details.connect(details)
        self.worker.succeeded.connect(callback)
        self.worker.failed.connect(self.notify)
        if on_error:
            self.worker.failed.connect(on_error)
        self.worker.finished.connect(self.job_finished)
        self.worker.start()

    def set_progress(self, value, stage):
        self.current_stage = stage
        self.status.setText(self.tr(stage))
        self.progress_anim.stop()
        self.progress_anim.setDuration(0 if self.reduced_motion() else 150)
        self.progress_anim.setStartValue(self.progressbar.value())
        self.progress_anim.setEndValue(value)
        self.progress_anim.start()

    def job_finished(self):
        self.busy = False
        self.current_stage = 'ready'
        self.pulse.stop()
        self.cancel_button.hide()
        self.status.setText(self.tr('ready'))
        if self.worker:
            self.worker.deleteLater()
            self.worker = None

    def cancel(self):
        if self.worker:
            self.worker.progress.event.set()
            self.status.setText(self.tr('cancelling'))

    def load_file(self, path):
        if self.busy:
            self.notify('busy')
            return
        media = str(Path(self.temp.name) / f'original-{os.urandom(6).hex()}.wav')
        def task(progress):
            audio = decode(path, progress)
            progress.update(95, 'preparing_playback')
            sf.write(media, audio.samples, audio.rate, subtype='FLOAT')
            return audio, media, waveform(audio.samples)
        self.run_job(task, self.loaded)

    def loaded(self, payload):
        self.audio, self.original_media, envelope = payload
        self.mastered = None
        self.master_metrics = None
        self.result = None
        self.master_media = ''
        self.player.stop()
        self.media_kind = 'original'
        self.player.setSource(QUrl.fromLocalFile(self.original_media))
        self.player_name.setText(Path(self.audio.path).name)
        self.seek.setRange(0, int(self.audio.duration*1000))
        positions, lower, upper = envelope
        times = positions / self.audio.rate
        self.wave_low.setData(times, lower)
        self.wave_high.setData(times, upper)
        self.wave.setXRange(0, self.audio.duration, padding=0)
        self.region.setBounds((0, self.audio.duration))
        self.region.setRegion((0, self.audio.duration))
        self.before_curve.setData(times, upper)
        self.after_curve.clear()
        self.spectrum_curve.clear()
        self.spec_image.clear()
        self.chroma_bars.setOpts(height=np.zeros(12))
        for card in self.cards:
            card.value.setText('—')
            card.detail.setText('—')
        self.warnings.clear()
        self.candidate_label.clear()
        self.peak_label.clear()
        self.update_comparison()
        self.update_file_info()
        self.position_changed(0)
        self.update_volume()
        self.notify('loaded')

    def update_file_info(self):
        if self.audio:
            self.file_info.setText(f'{Path(self.audio.path).name}\n{self.audio.duration:.1f} s  ·  {self.audio.rate:,} Hz  ·  {self.audio.samples.shape[1]} {self.tr("channels")}  ·  {Path(self.audio.path).suffix.upper()[1:]}  ·  {Path(self.audio.path).stat().st_size/1024**2:.1f} MB' if Path(self.audio.path).exists() else self.tr('missing_file'))
        else:
            self.file_info.setText(self.tr('no_file'))

    def start_analysis(self, selection=False):
        if not self.audio:
            self.notify('load_first')
            return
        if self.busy:
            self.notify('busy')
            return
        audio = self.audio
        start, end = self.region.getRegion() if selection else (0, audio.duration)
        quality = self.settings.value('quality', 'full')
        if self.settings.value('performance', 'normal') == 'economy':
            quality = 'quick'
        self.navigate(1)
        def done(result):
            self.result = result
            self.display_result(result)
            try:
                self.history.add(audio.path, result)
                self.refresh_history()
            except OSError:
                self.notify('write_error')
        self.run_job(lambda progress: analyze(audio, start, end, quality, progress), done)

    def key_name(self, key):
        return key['root'] + ' ' + self.tr('minor' if key['minor'] else 'major') if key else self.tr('undetermined')

    def display_result(self, result, animate=True):
        key = result['key']
        self.cards[0].value.setText(self.key_name(key))
        self.cards[0].detail.setText(f'{key["root"]}{"m" if key["minor"] else ""}  ·  Camelot {key["camelot"]}\n{self.tr("relative")}: {key["relative"]} {self.tr("major" if key["minor"] else "minor")}' if key else self.tr('no_key'))
        bpm = result['bpm']
        self.cards[1].value.setText(f'{bpm:.1f} BPM' if bpm else '—')
        self.cards[1].detail.setText(f'½ {bpm/2:.1f}  ·  2× {bpm*2:.1f}\n{self.tr("heuristic")}: {result["tempo_confidence"]:.0%}' if bpm else self.tr('uncertain_tempo'))
        dominant = result['dominant']
        self.cards[2].value.setText(f'{dominant:.1f} Hz' if dominant else '—')
        pitch = result['pitch']
        self.cards[2].detail.setText(f'{self.tr("sample_rate")}: {result["rate"]:,} Hz\n{self.tr("pitch")}: ' + (f'{pitch["note"]} ({pitch["hz"]:.1f} Hz)' if pitch else self.tr('undetermined')))
        self.cards[3].value.setText(f'{result["confidence"]:.0%}')
        self.cards[3].detail.setText(self.tr('confidence_note'))
        self.warnings.setText(' · '.join(self.tr(key) for key in result['warnings']))
        self.chroma_bars.setOpts(height=result['chroma'])
        self.candidate_label.setText(self.tr('candidates') + ':  ' + '   /   '.join(f'{self.key_name(c)} ({c["score"]:.2f})' for c in result['candidates']))
        self.peak_label.setText(self.tr('spectral_peaks') + ': ' + ', '.join(f'{p:.1f} Hz' for p in result.get('peaks', [])))
        if result.get('frequency'):
            self.spectrum_curve.setData(result['frequency'][1:], result['spectrum'][1:])
        else:
            self.spectrum_curve.clear()
        if result.get('spectrogram'):
            from PySide6.QtCore import QRectF
            self.spec_image.setImage(np.asarray(result['spectrogram']), levels=(-80, 0))
            self.spec_image.setRect(QRectF(result['start'], 0, result['end']-result['start'], 11025))
        else:
            self.spec_image.clear()
        if animate:
            self.animate_page()

    def preset_changed(self, index):
        preset = self.presets.itemData(index)
        if not hasattr(self, 'controls') or preset == 'custom':
            return
        target, width, eq, compression, _ = PRESETS[preset]
        for key, value in [('target',target), ('width',width*100), ('eq',eq*100), ('compression',compression*100)]:
            self.controls[key].setValue(value)

    def toggle_advanced(self):
        self.advanced_animation.stop()
        self.advanced_animation.setDuration(0 if self.reduced_motion() else 220)
        self.advanced_animation.setStartValue(self.advanced.maximumHeight())
        self.advanced_animation.setEndValue(120 if self.advanced.maximumHeight() == 0 else 0)
        self.advanced_animation.start()

    def start_mastering(self):
        if not self.audio:
            self.notify('load_first')
            return
        values = {key: widget.value() for key, widget in self.controls.items()}
        settings = MasterSettings(self.presets.currentData(), values['intensity']/100, values['target'],
                                  values['width']/100, values['eq']/100, values['compression']/100, values['ceiling'])
        if settings.target > -10 or settings.width > 1.3:
            self.notify('aggressive')
        audio = self.audio
        media = str(Path(self.temp.name) / f'master-{os.urandom(6).hex()}.wav')
        def task(progress):
            result, metrics = master(audio, settings, progress)
            sf.write(media, result.samples, result.rate, subtype='FLOAT')
            return result, metrics, media, waveform(result.samples), settings.ceiling
        self.run_job(task, self.master_done)

    def master_done(self, payload):
        self.mastered, self.master_metrics, self.master_media, envelope, self.master_ceiling = payload
        times, lower, upper = envelope
        self.after_curve.setData(times/self.mastered.rate, upper)
        self.update_comparison()
        if self.master_metrics['target_limited']:
            self.notify('target_limited')
        self.switch_media('mastered')

    def update_comparison(self):
        if not self.master_metrics:
            self.compare_label.setText(self.tr('no_master'))
            return
        lines = []
        for key, label in [('before', 'original'), ('after', 'mastered')]:
            metrics = self.master_metrics[key]
            lines.append(f'{self.tr(label)}: {metrics["lufs"]:.1f} LUFS  ·  {metrics["true_peak"]:.2f} dBTP  ·  {self.tr("crest")}: {metrics["crest"]:.1f} dB')
        self.compare_label.setText('\n'.join(lines))

    def switch_media(self, kind):
        path = self.original_media if kind == 'original' else self.master_media
        if not path:
            self.notify('load_first' if kind == 'original' else 'no_master')
            return
        if kind == self.media_kind:
            return
        position = self.player.position()
        playing = self.player.playbackState() == QMediaPlayer.PlayingState
        self.media_kind = kind
        self.pending_seek = (position, playing)
        self.player.setSource(QUrl.fromLocalFile(path))
        self.player_name.setText(f'{Path(self.audio.path).name}  ·  {self.tr(kind)}')
        self.update_volume()

    def media_loaded(self, status):
        if status in (QMediaPlayer.LoadedMedia, QMediaPlayer.BufferedMedia) and self.pending_seek:
            position, playing = self.pending_seek
            self.pending_seek = None
            self.player.setPosition(position)
            if playing:
                self.player.play()

    def update_volume(self, *_):
        gain = self.volume.value()/100
        if self.master_metrics and self.match.isChecked():
            a = self.master_metrics['before']['lufs']
            b = self.master_metrics['after']['lufs']
            current = a if self.media_kind == 'original' else b
            gain *= 10 ** ((min(a, b)-current)/20)
        self.output.setVolume(gain)

    def play(self):
        self.vocal_page.player.pause()
        if not self.audio:
            self.notify('load_first')
        elif not QMediaDevices.audioOutputs():
            self.notify('no_device')
        else:
            self.player.play()

    def position_changed(self, position):
        if not self.seek.isSliderDown():
            self.seek.setValue(position)
        self.playhead.setValue(position/1000)
        duration = self.audio.duration if self.audio else 0
        self.time_label.setText(f'{int(position/60000):02}:{int(position/1000)%60:02} / {int(duration/60):02}:{int(duration)%60:02}')

    def wave_click(self, event):
        if event.double() and self.audio:
            point = self.wave.plotItem.vb.mapSceneToView(event.scenePos())
            self.player.setPosition(int(np.clip(point.x(), 0, self.audio.duration)*1000))

    def export_master(self):
        if not self.mastered:
            self.notify('no_master')
            return
        if self.busy:
            self.notify('busy')
            return
        dialog = QDialog(self)
        dialog.setWindowTitle(self.tr('export_master'))
        layout = QFormLayout(dialog)
        fmt = QComboBox()
        fmt.addItems(['WAV', 'FLAC', 'MP3'])
        fmt.setCurrentText(self.settings.value('export_format', 'wav').upper())
        rate = QComboBox()
        rate.addItems(['22050', '32000', '44100', '48000', '88200', '96000', '192000'])
        rate.setCurrentText(str(self.mastered.rate) if str(self.mastered.rate) in [rate.itemText(i) for i in range(rate.count())] else '48000')
        depth = QComboBox()
        depth.addItems(['16-bit PCM', '24-bit PCM', '32-bit float'])
        depth.setCurrentIndex(1)
        bitrate = QComboBox()
        bitrate.addItems(['128', '192', '256', '320'])
        bitrate.setCurrentText('320')
        for key, widget in [('format',fmt), ('sample_rate',rate), ('bit_depth',depth), ('mp3_quality',bitrate)]:
            layout.addRow(self.tr(key), widget)
        note = QLabel(self.tr('export_note'))
        note.setWordWrap(True)
        layout.addRow(note)
        buttons = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        buttons.button(QDialogButtonBox.Save).setText(self.tr('save'))
        buttons.button(QDialogButtonBox.Cancel).setText(self.tr('cancel'))
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addRow(buttons)
        if dialog.exec() != QDialog.Accepted:
            return
        extension = fmt.currentText().lower()
        default = Path(self.settings.value('export_folder', str(Path.home()/'Music'))) / (Path(self.audio.path).stem + '-KEYWAVE.' + extension)
        path, _ = QFileDialog.getSaveFileName(self, self.tr('export_master'), str(default), f'{extension.upper()} (*.{extension})')
        if not path:
            return
        if Path(path).suffix.lower() != '.' + extension:
            path += '.' + extension
        audio = self.mastered
        subtype = ('PCM_16','PCM_24','FLOAT')[depth.currentIndex()]
        selected_rate, selected_bitrate, ceiling = int(rate.currentText()), int(bitrate.currentText()), self.master_ceiling
        self.run_job(lambda progress: export_audio(audio, path, selected_rate, subtype, selected_bitrate, progress, ceiling), lambda _: self.notify('exported'))

    def export_report(self):
        if not self.result:
            self.notify('analyze_first')
            return
        path, selected = QFileDialog.getSaveFileName(self, self.tr('export_report'), 'KEYWAVE-analysis.json', 'JSON (*.json);;CSV (*.csv)')
        if not path:
            return
        try:
            result = {k:v for k,v in self.result.items() if k not in ('spectrogram','frequency','spectrum')}
            if 'CSV' in selected:
                with open(path, 'w', newline='', encoding='utf-8-sig') as stream:
                    writer = csv.writer(stream)
                    writer.writerow(['metric','value'])
                    for key, value in result.items():
                        writer.writerow([key, json.dumps(value, ensure_ascii=False)])
            else:
                atomic_json(Path(path), result)
            self.notify('exported')
        except OSError:
            self.notify('write_error')

    def refresh_history(self):
        self.history_list.clear()
        self.recent.clear()
        for entry in self.history.entries:
            result = entry['result']
            bpm = result.get('bpm')
            self.history_list.addItem(f'{Path(entry["file"]).name}  ·  {self.key_name(result.get("key"))}  ·  {f"{bpm:.1f} BPM" if bpm else "—"}\n{entry["date"][:16].replace("T", " ")} UTC')
            self.history_list.item(self.history_list.count()-1).setData(Qt.UserRole, entry['id'])
        seen = set()
        for entry in self.history.entries:
            if entry['file'] in seen:
                continue
            seen.add(entry['file'])
            self.recent.addItem(Path(entry['file']).name)
            self.recent.item(self.recent.count()-1).setData(Qt.UserRole, entry['file'])
            if len(seen) == 5:
                break

    def selected_entry(self):
        item = self.history_list.currentItem()
        if item:
            return next((e for e in self.history.entries if e['id'] == item.data(Qt.UserRole)), None)
        self.notify('select_history')
        return None

    def show_history(self):
        entry = self.selected_entry()
        if entry:
            dialog = QDialog(self)
            dialog.setWindowTitle(self.tr('view_result'))
            layout = QVBoxLayout(dialog)
            result = entry['result']
            text = QLabel(f'{Path(entry["file"]).name}\n\n{self.key_name(result.get("key"))}\n{result.get("bpm") or "—"} BPM\n{self.tr("confidence")}: {result["confidence"]:.0%}\n{self.tr("time")}: {result["start"]:.1f}–{result["end"]:.1f} s\n\n' + '\n'.join(self.tr(w) for w in result['warnings']))
            text.setWordWrap(True)
            layout.addWidget(text)
            close = Button(self.tr('close'))
            close.clicked.connect(dialog.accept)
            layout.addWidget(close)
            dialog.exec()

    def reanalyze_history(self):
        entry = self.selected_entry()
        if entry and not self.busy:
            self.load_file(entry['file'])
            if self.worker:
                self.worker.finished.connect(lambda: QTimer.singleShot(0, self.start_analysis) if self.audio and self.audio.path == str(Path(entry['file']).resolve()) else None)

    def delete_history(self):
        entry = self.selected_entry()
        if entry:
            try:
                self.history.remove(entry['id'])
                self.refresh_history()
            except OSError:
                self.notify('write_error')

    def clear_history(self):
        box = QMessageBox(self)
        box.setWindowTitle(self.tr('clear_history'))
        box.setText(self.tr('confirm_clear'))
        yes = box.addButton(self.tr('delete'), QMessageBox.AcceptRole)
        box.addButton(self.tr('cancel'), QMessageBox.RejectRole)
        box.exec()
        if box.clickedButton() == yes:
            try:
                self.history.clear()
                self.refresh_history()
            except OSError:
                self.notify('write_error')

    def save_preference(self, key, value):
        self.settings.setValue(key, value)
        self.settings.sync()
        self.apply_preferences()

    def apply_preferences(self):
        for button in self.buttons + [self.dropzone.button]:
            button.motion = not self.reduced_motion()
        self.setStyleSheet(STYLE + ('QLabel#muted {color:#E2D9EF;} QFrame#card {border:1px solid #8B5CF6;}' if self.settings.value('theme') == 'contrast' else ''))
        self.device_changed()

    def device_changed(self, *_):
        selected = self.devices.currentData()
        self.settings.setValue('device', selected)
        devices = QMediaDevices.audioOutputs()
        device = next((d for d in devices if bytes(d.id()).hex() == selected), QMediaDevices.defaultAudioOutput())
        self.output.setDevice(device)

    def choose_folder(self):
        folder = QFileDialog.getExistingDirectory(self, self.tr('export_folder'), self.export_folder.text())
        if folder:
            self.export_folder.setText(folder)
            self.save_preference('export_folder', folder)

    def reset_settings(self):
        self.settings.clear()
        self.language.setCurrentIndex(0)
        for widget in self.pref_widgets.values():
            widget.setCurrentIndex(0)
        self.reduced.setChecked(False)
        self.devices.setCurrentIndex(0)
        self.export_folder.setText(str(Path.home()/'Music'))
        self.apply_preferences()
        self.notify('settings_reset')

    def closeEvent(self, event):
        if self.busy:
            self.cancel()
            self.notify('wait_cancel')
            event.ignore()
            return
        self.player.stop()
        self.player.setSource(QUrl())
        self.vocal_page.stop()
        self.settings.sync()
        try:
            self.temp.cleanup()
        except OSError:
            logging.warning('Playback temporary files still in use')
        event.accept()
