"""Compact vocal correction controls; processing uses the shared job coordinator."""
from pathlib import Path
import os
import numpy as np
import soundfile as sf
import pyqtgraph as pg
from PySide6.QtCore import Qt, QUrl, QPropertyAnimation
from PySide6.QtMultimedia import QMediaPlayer, QAudioOutput
from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QFormLayout, QLabel, QComboBox, QDoubleSpinBox, QSlider, QCheckBox, QFileDialog

from ..audio import decode, waveform, export_audio
from ..autotune import TuneSettings, VOCAL_PRESETS
from .widgets import DropZone


class VocalPage(QWidget):
    def __init__(self, host):
        super().__init__()
        self.host = host
        self.audio = self.tuned = self.report = None
        self.sources = {}
        self.kind = 'original'
        self.pending = None
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0,0,0,0)
        layout.setSpacing(12)
        self.drop = DropZone()
        self.drop.setMinimumHeight(100)
        host.bindings.extend([(self.drop.title.setText,'vocal_drop'), (self.drop.subtitle.setText,'vocal_formats'), (self.drop.button.setText,'vocal_import')])
        self.drop.browse.connect(self.browse)
        self.drop.dropped.connect(self.load)
        layout.addWidget(self.drop)
        self.info = QLabel('—')
        self.info.setWordWrap(True)
        layout.addWidget(self.info)
        controls = QHBoxLayout()
        self.key = QComboBox()
        self.key.addItems(['C','C#','D','D#','E','F','F#','G','G#','A','A#','B'])
        self.key.setCurrentIndex(5)
        self.scale = QComboBox()
        for name in ('minor','major','chromatic'):
            self.scale.addItem(host.tr(name), name)
        self.bpm = QDoubleSpinBox()
        self.bpm.setRange(40,300)
        self.bpm.setDecimals(1)
        self.bpm.setValue(139)
        self.bpm.setSuffix(' BPM')
        self.bpm.valueChanged.connect(self.beat_grid)
        for name, widget in [('vocal_key',self.key), ('vocal_scale',self.scale), ('tempo',self.bpm)]:
            controls.addWidget(host.label(name))
            controls.addWidget(widget,1)
        layout.addLayout(controls)
        strength_row = QHBoxLayout()
        strength_row.addWidget(host.label('vocal_strength'))
        self.strength = QSlider(Qt.Horizontal)
        self.strength.setRange(0,100)
        self.strength.setValue(65)
        self.strength_value = QLabel('65%')
        self.strength_value.setObjectName('metric')
        self.strength_value.setFixedWidth(80)
        self.strength.valueChanged.connect(lambda value: self.strength_value.setText(f'{value}%'))
        strength_row.addWidget(self.strength,1)
        strength_row.addWidget(self.strength_value)
        layout.addLayout(strength_row)
        preset_row = QHBoxLayout()
        self.preset = QComboBox()
        for name in VOCAL_PRESETS:
            self.preset.addItem(host.tr(name), name)
        self.preset.setCurrentIndex(1)
        self.preset.currentIndexChanged.connect(self.set_preset)
        preset_row.addWidget(self.preset,1)
        preset_row.addWidget(host.button('vocal_process',self.process,True),1)
        preset_row.addWidget(host.button('vocal_advanced',self.toggle_advanced))
        layout.addLayout(preset_row)
        self.advanced = QWidget()
        self.advanced.setMaximumHeight(0)
        form = QFormLayout(self.advanced)
        self.speed = QComboBox()
        for name in ('natural','fast','instant'):
            self.speed.addItem(host.tr(name),name)
        form.addRow(host.label('retune_speed'),self.speed)
        self.humanize = QSlider(Qt.Horizontal)
        self.humanize.setRange(0,100)
        self.humanize.setValue(50)
        self.humanize_value = QLabel('50%')
        human_row = QHBoxLayout()
        human_row.addWidget(self.humanize)
        human_row.addWidget(self.humanize_value)
        self.humanize.valueChanged.connect(lambda value:self.humanize_value.setText(f'{value}%'))
        form.addRow(host.label('humanize'),human_row)
        self.formants = QCheckBox()
        self.formants.setChecked(True)
        form.addRow(host.label('preserve_formants'),self.formants)
        form.addRow(host.label('vocal_method','muted'))
        layout.addWidget(self.advanced)
        self.animation = QPropertyAnimation(self.advanced,b'maximumHeight',self)
        self.wave = host.plot(110)
        self.wave.setMaximumHeight(150)
        self.wave_original = self.wave.plot(pen='#4C9BD8')
        self.wave_processed = self.wave.plot(pen='#78B8E6')
        self.playhead = pg.InfiniteLine(0,pen='#4C7699')
        self.wave.addItem(self.playhead)
        self.beats = pg.PlotCurveItem(pen=pg.mkPen('#BDD8EA',width=1),connect='pairs')
        self.wave.addItem(self.beats)
        self.wave.scene().sigMouseClicked.connect(self.seek)
        layout.addWidget(self.wave)
        self.output = QAudioOutput(self)
        self.output.setVolume(.8)
        self.player = QMediaPlayer(self)
        self.player.setAudioOutput(self.output)
        self.player.positionChanged.connect(lambda position:self.playhead.setValue(position/1000))
        self.player.mediaStatusChanged.connect(self.restore_position)
        self.player.errorOccurred.connect(lambda *_:host.notify('playback_error'))
        playback = QHBoxLayout()
        playback.addWidget(host.button('original',lambda:self.switch('original')))
        playback.addWidget(host.button('auto_tuned',lambda:self.switch('auto_tuned')))
        playback.addWidget(host.button('play',self.play))
        playback.addWidget(host.button('pause',self.player.pause))
        layout.addLayout(playback)
        self.listening = host.label('original','muted')
        layout.addWidget(self.listening)
        export_row = QHBoxLayout()
        export_row.addWidget(host.button('vocal_export_wav',lambda:self.export('wav')))
        export_row.addWidget(host.button('vocal_export_mp3',lambda:self.export('mp3')))
        self.bitrate = QComboBox()
        self.bitrate.addItems(['128','192','256','320'])
        self.bitrate.setCurrentText('192')
        export_row.addWidget(host.label('mp3_quality'))
        export_row.addWidget(self.bitrate)
        layout.addLayout(export_row)
        self.pitch = host.plot(160)
        self.pitch_before = self.pitch.plot(pen='#4C9BD8',connect='finite')
        self.pitch_after = self.pitch.plot(pen='#78B8E6',connect='finite')
        layout.addWidget(self.pitch)
        layout.addWidget(host.label('vocal_pitch_note','muted'))
        layout.addStretch()

    def translate(self):
        for combo in (self.scale,self.speed,self.preset):
            for index in range(combo.count()):
                combo.setItemText(index,self.host.tr(combo.itemData(index)))
        self.listening.setText(self.host.tr(self.kind))
        self.wave.setLabel('bottom',self.host.tr('time'),units='s')
        self.pitch.setLabel('bottom',self.host.tr('time'),units='s')
        self.pitch.setLabel('left',self.host.tr('pitch'),units='Hz')
        self.drop.button.motion = not self.host.reduced_motion()

    def browse(self):
        path,_ = QFileDialog.getOpenFileName(self,self.host.tr('vocal_import'),'','Audio (*.wav *.mp3 *.flac *.m4a)')
        if path:
            self.load(path)

    def load(self,path):
        if self.host.busy:
            self.host.notify('busy')
            return
        media = str(Path(self.host.temp.name)/f'vocal-{os.urandom(6).hex()}.wav')
        def job(progress):
            audio = decode(path,progress)
            sf.write(media,audio.samples,audio.rate,subtype='FLOAT')
            return audio,waveform(audio.samples)
        def done(payload):
            self.audio, envelope = payload
            self.tuned = self.report = None
            self.host.player.pause()
            self.player.stop()
            self.sources = {'original':media}
            self.kind = 'original'
            self.pending = None
            self.player.setSource(QUrl.fromLocalFile(media))
            x,lower,upper = envelope
            self.wave_original.setData(x/self.audio.rate,upper)
            self.wave_processed.clear()
            self.pitch_before.clear()
            self.pitch_after.clear()
            self.wave.setXRange(0,self.audio.duration,padding=0)
            self.info.setText(f'{Path(path).name}  ·  {self.audio.duration:.1f} s  ·  {self.audio.rate:,} Hz')
            self.beat_grid()
            self.translate()
        self.host.run_job(job,done)

    def set_preset(self,index):
        strength,speed,humanize = VOCAL_PRESETS[self.preset.itemData(index)]
        self.strength.setValue(round(strength*100))
        self.speed.setCurrentIndex(self.speed.findData(speed))
        self.humanize.setValue(round(humanize*100))

    def toggle_advanced(self):
        self.animation.stop()
        self.animation.setDuration(0 if self.host.reduced_motion() else 200)
        self.animation.setStartValue(self.advanced.maximumHeight())
        self.animation.setEndValue(240 if self.advanced.maximumHeight() == 0 else 0)
        self.animation.start()

    def beat_grid(self,*_):
        if self.audio:
            # Tempo is only a visual synchronization grid; it cannot change pitch targets.
            values = np.arange(0,self.audio.duration,60/self.bpm.value())[:5000]
            self.beats.setData(np.repeat(values,2),np.tile([-.95,.95],len(values)))

    def process(self):
        from ..autotune import tune_vocal
        if not self.audio:
            self.host.notify('vocal_load_first')
            return
        audio = self.audio
        settings = TuneSettings(self.key.currentIndex(),self.scale.currentData(),self.bpm.value(),
            self.strength.value()/100,self.speed.currentData(),self.humanize.value()/100,self.formants.isChecked())
        media = str(Path(self.host.temp.name)/f'tuned-{os.urandom(6).hex()}.wav')
        def job(progress):
            tuned,report = tune_vocal(audio,settings,progress)
            sf.write(media,tuned.samples,tuned.rate,subtype='FLOAT')
            return tuned,report,waveform(tuned.samples)
        def done(payload):
            self.tuned,self.report,envelope = payload
            self.sources['auto_tuned'] = media
            x,lower,upper = envelope
            self.wave_processed.setData(x/audio.rate,upper)
            self.pitch_before.setData(self.report['times'],np.array(self.report['input_hz'],dtype=float))
            self.pitch_after.setData(self.report['times'],np.array(self.report['output_hz'],dtype=float))
            self.switch('auto_tuned')
            self.host.notify('vocal_bypass' if self.report['bypass'] else ('vocal_done' if self.report['voiced_fraction'] > .05 else 'vocal_no_pitch'))
        self.host.run_job(job,done)

    def switch(self,kind):
        if kind not in self.sources:
            self.host.notify('vocal_process_first' if kind == 'auto_tuned' else 'vocal_load_first')
            return
        self.pending = (self.player.position(),self.player.playbackState() == QMediaPlayer.PlayingState)
        self.kind = kind
        self.player.setSource(QUrl.fromLocalFile(self.sources[kind]))
        self.listening.setText(self.host.tr(kind))

    def restore_position(self,status):
        if self.pending and status in (QMediaPlayer.LoadedMedia,QMediaPlayer.BufferedMedia):
            position,playing = self.pending
            self.pending = None
            self.player.setPosition(position)
            if playing:
                self.player.play()

    def play(self):
        if not self.audio:
            self.host.notify('vocal_load_first')
            return
        self.host.player.pause()
        self.output.setDevice(self.host.output.device())
        self.output.setVolume(self.host.output.volume())
        self.output.setMuted(self.host.output.isMuted())
        self.player.play()

    def seek(self,event):
        if event.double() and self.audio:
            point = self.wave.plotItem.vb.mapSceneToView(event.scenePos())
            self.player.setPosition(round(np.clip(point.x(),0,self.audio.duration)*1000))

    def export(self,extension):
        if not self.tuned:
            self.host.notify('vocal_process_first')
            return
        if self.host.busy:
            self.host.notify('busy')
            return
        folder = Path(self.host.settings.value('export_folder',str(Path.home()/'Music')))
        suggested = folder/(Path(self.tuned.path).stem+'-tuned.'+extension)
        path,_ = QFileDialog.getSaveFileName(self,self.host.tr('save_as'),str(suggested),f'{extension.upper()} (*.{extension})')
        if not path:
            return
        if Path(path).suffix.lower() != '.'+extension:
            path += '.'+extension
        audio,bitrate = self.tuned,int(self.bitrate.currentText())
        self.host.run_job(lambda progress:export_audio(audio,path,audio.rate,'PCM_24',bitrate,progress),lambda _:self.host.notify('exported'))

    def stop(self):
        self.player.stop()
        self.player.setSource(QUrl())
