"""Packaged end-to-end test. Uses only generated fixtures and a temporary settings store."""
from pathlib import Path
import json
import os
import traceback
import numpy as np
import soundfile as sf
from PySide6.QtCore import QTimer
from .audio import export_audio, decode
from .core import Audio


def run_smoke(app, window):
    directory = Path(os.environ.get('KEYWAVE_SMOKE_DIR', 'artifacts')).resolve()
    directory.mkdir(parents=True, exist_ok=True)
    rate = 22050
    t = np.arange(rate*10)/rate
    signal = (.12*np.sin(2*np.pi*261.625565*t) + .08*np.sin(2*np.pi*329.627557*t) + .08*np.sin(2*np.pi*391.995436*t)).astype(np.float32)
    click = .3*np.sin(2*np.pi*1000*np.arange(500)/rate)*np.exp(-np.arange(500)/60)
    for start in range(0,len(signal)-500,rate//2):
        signal[start:start+500] += click
    source = directory/'smoke-source.wav'
    sf.write(source, signal, rate)
    state = {'stage':0, 'ticks':0, 'playback_position':0}
    capture_screenshots = os.environ.get('KEYWAVE_CAPTURE_SCREENSHOTS') == '1'
    def capture(filename):
        # Qt's offscreen renderer can crash the native process on Windows CI.
        # Desktop screenshots are optional; smoke verification tests functionality.
        if capture_screenshots:
            window.grab().save(str(directory/filename))
    window.reduced.setChecked(True)
    timer = QTimer(window)
    timer.setInterval(150)
    def fail(error):
        (directory/'smoke-result.json').write_text(json.dumps({'ok':False,'error':str(error),'traceback':traceback.format_exc()}), encoding='utf-8')
        timer.stop()
        if window.worker:
            window.worker.progress.event.set()
            window.worker.wait(30000)
        app.exit(1)
    def tick():
        try:
            state['ticks'] += 1
            (directory/'smoke-stage.txt').write_text(str(state['stage']), encoding='utf-8')
            if state['ticks'] > 1800:
                raise RuntimeError('Smoke test timeout')
            if window.busy:
                return
            stage = state['stage']
            if stage == 0:
                capture('dashboard.png')
                window.load_file(str(source))
            elif stage == 1:
                assert window.audio is not None, window.notice.text()
                window.start_analysis()
            elif stage == 2:
                assert window.result is not None, window.notice.text()
                assert window.result['bpm'] and window.result['key']
                capture('analyzer.png')
                window.navigate(2)
                window.start_mastering()
            elif stage == 3:
                assert window.mastered is not None, window.notice.text()
                capture('mastering.png')
                export_audio(window.mastered, str(directory/'smoke-master.wav'), 44100, ceiling=-1)
                export_audio(window.mastered, str(directory/'smoke-master.mp3'), 44100)
                assert decode(str(directory/'smoke-master.mp3')).duration > 9
                window.play()
                state['playback_start'] = state['ticks']
            elif stage == 4:
                if state['ticks'] - state['playback_start'] < 15:
                    return
                state['playback_position'] = window.player.position()
                window.player.pause()
                window.switch_media('original')
                window.language.setCurrentIndex(1)
                window.navigate(0)
            elif stage == 5:
                capture('dashboard-ru.png')
                t = np.arange(rate*2)/rate
                vocal = directory/'smoke-vocal.wav'
                sf.write(vocal,.2*np.sin(2*np.pi*280*t),rate)
                window.navigate(6)
                window.vocal_page.load(str(vocal))
            elif stage == 6:
                vocal = window.vocal_page
                assert vocal.audio is not None,window.notice.text()
                vocal.key.setCurrentIndex(0)
                vocal.scale.setCurrentIndex(1)
                vocal.strength.setValue(100)
                vocal.speed.setCurrentIndex(2)
                vocal.humanize.setValue(0)
                vocal.process()
            elif stage == 7:
                from scipy.signal import welch
                from .core import resource
                import subprocess
                import yt_dlp
                import yt_dlp_ejs
                vocal = window.vocal_page
                assert vocal.tuned is not None,window.notice.text()
                frequency,power = welch(vocal.tuned.samples[rate//2:rate*3//2,0],rate,nperseg=16384)
                state['vocal_hz'] = float(frequency[np.argmax(power)])
                assert abs(state['vocal_hz']-293.6648) < 3
                export_audio(vocal.tuned,str(directory/'smoke-tuned.wav'),rate,'PCM_24')
                export_audio(vocal.tuned,str(directory/'smoke-tuned.mp3'),rate,'PCM_24',192)
                assert decode(str(directory/'smoke-tuned.mp3')).duration > 1.9
                node = subprocess.run([str(resource('runtime/node.exe')),'--version'],capture_output=True,check=True,
                    creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
                state['node_version'] = node.stdout.decode().strip()
                capture('vocal-studio.png')
                window.navigate(5)
            elif stage == 8:
                capture('youtube-downloader.png')
                (directory/'smoke-result.json').write_text(json.dumps({'ok':True,
                    'key':window.result['key'], 'bpm':window.result['bpm'],
                    'master':window.master_metrics, 'playback_position_ms':state['playback_position'],
                    'vocal_hz':state['vocal_hz'],'node_version':state['node_version']},indent=2), encoding='utf-8')
                timer.stop()
                window.close()
                app.quit()
                return
            state['stage'] += 1
        except Exception as error:
            fail(error)
    timer.timeout.connect(tick)
    timer.start()
