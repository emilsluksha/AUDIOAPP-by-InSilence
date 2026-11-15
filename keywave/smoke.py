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
            if state['ticks'] > 1800:
                raise RuntimeError('Smoke test timeout')
            if window.busy:
                return
            stage = state['stage']
            if stage == 0:
                window.grab().save(str(directory/'dashboard.png'))
                window.load_file(str(source))
            elif stage == 1:
                assert window.audio is not None, window.notice.text()
                window.start_analysis()
            elif stage == 2:
                assert window.result is not None, window.notice.text()
                assert window.result['bpm'] and window.result['key']
                window.grab().save(str(directory/'analyzer.png'))
                window.navigate(2)
                window.start_mastering()
            elif stage == 3:
                assert window.mastered is not None, window.notice.text()
                window.grab().save(str(directory/'mastering.png'))
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
                window.grab().save(str(directory/'dashboard-ru.png'))
                (directory/'smoke-result.json').write_text(json.dumps({'ok':True,
                    'key':window.result['key'], 'bpm':window.result['bpm'],
                    'master':window.master_metrics, 'playback_position_ms':state['playback_position']},indent=2), encoding='utf-8')
                timer.stop()
                window.close()
                app.quit()
                return
            state['stage'] += 1
        except Exception as error:
            fail(error)
    timer.timeout.connect(tick)
    timer.start()
