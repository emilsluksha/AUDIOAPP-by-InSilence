from pathlib import Path
import numpy as np
import pytest
import soundfile as sf

from keywave.core import Audio, AudioError, Cancelled, Progress
from keywave.audio import decode, export_audio, run_codec
from keywave.analysis import analyze, key_scores, MAJOR, MINOR
from keywave.mastering import master, MasterSettings, PRESETS, true_peak
from keywave.storage import History, Translator


def tone(hz=440, duration=3, rate=22050):
    t = np.arange(int(rate*duration))/rate
    return Audio((.2*np.sin(2*np.pi*hz*t)).astype(np.float32)[:,None], rate, 'original.wav')


@pytest.fixture(scope='module')
def tonal_result():
    return analyze(tone())


def test_wav_decode(tmp_path):
    source = tone()
    path = tmp_path/'source.wav'
    sf.write(path, source.samples, source.rate, subtype='FLOAT')
    audio = decode(str(path))
    assert audio.rate == source.rate
    np.testing.assert_allclose(audio.samples, source.samples)


def test_mp3_decode_and_export(tmp_path):
    source = tone()
    path = tmp_path/'source.mp3'
    export_audio(source, str(path), source.rate)
    audio = decode(str(path))
    assert abs(audio.duration-source.duration) < .15
    assert np.max(np.abs(audio.samples)) > .1


def test_corrupt(tmp_path):
    path = tmp_path/'broken.mp3'
    path.write_bytes(b'not an audio file')
    with pytest.raises(AudioError):
        decode(str(path))


def test_frequency_pitch(tonal_result):
    assert abs(tonal_result['dominant']-440) < 2
    assert tonal_result['pitch']['note'] == 'A4'
    assert abs(tonal_result['pitch']['hz']-440) < 3


@pytest.mark.parametrize('profile,minor', [(MAJOR,False),(MINOR,True)])
@pytest.mark.parametrize('root', range(12))
def test_all_key_profiles(profile, minor, root):
    result = key_scores(np.roll(profile, root))[0]
    from keywave.analysis import NOTES
    assert result['root'] == NOTES[root]
    assert result['minor'] == minor


def test_harmonic_key():
    rate = 22050
    t = np.arange(rate*12)/rate
    # C-major tonal profile rendered as simultaneous harmonic partials.
    y = np.zeros_like(t)
    for note, weight in enumerate(MAJOR):
        hz = 261.625565 * 2**(note/12)
        y += weight/100*np.sin(2*np.pi*hz*t)
    result = analyze(Audio(y.astype(np.float32)[:,None], rate, 'major.wav'))
    assert result['key'] is not None
    assert result['key']['root'] == 'C'
    assert not result['key']['minor']


def test_bpm():
    sr = 22050
    samples = np.zeros(sr*16, dtype=np.float32)
    click = np.sin(2*np.pi*1000*np.arange(500)/sr)*np.exp(-np.arange(500)/60)
    for start in range(0, len(samples)-500, sr//2):
        samples[start:start+500] = click
    result = analyze(Audio(samples[:,None], sr, 'beat.wav'))
    assert result['bpm'] is not None
    assert abs(result['bpm']-120) < 4


def test_silence():
    audio = Audio(np.zeros((22050,2), dtype=np.float32), 22050, 'silence.wav')
    result = analyze(audio)
    assert result['key'] is None and result['bpm'] is None
    assert result['metrics']['lufs'] is None
    with pytest.raises(AudioError, match='silence'):
        master(audio, MasterSettings())


@pytest.mark.parametrize('preset', list(PRESETS))
def test_mastering_finite_peaks(preset):
    audio = tone(duration=2)
    audio.samples = np.column_stack((audio.samples[:,0], audio.samples[:,0]*.7))
    target, width, eq, compression, _ = PRESETS[preset]
    result, report = master(audio, MasterSettings(preset, 1, target, width, eq, compression, -1))
    assert np.isfinite(result.samples).all()
    assert true_peak(result.samples) <= 10**(-1/20)+1e-6
    assert report['after']['lufs'] is not None
    assert not np.allclose(audio.samples, result.samples)


def test_presets_different_and_bypass():
    audio = tone(duration=2)
    a, _ = master(audio, MasterSettings(preset='smooth'))
    b, _ = master(audio, MasterSettings(preset='vocal'))
    assert not np.allclose(a.samples,b.samples)
    bypass, _ = master(audio, MasterSettings(intensity=0))
    np.testing.assert_allclose(bypass.samples, audio.samples, atol=2e-7)


@pytest.mark.parametrize('extension,subtype', [('wav','PCM_16'),('wav','PCM_24'),('wav','FLOAT'),('flac','PCM_24')])
def test_export(tmp_path, extension, subtype):
    audio, _ = master(tone(duration=1), MasterSettings())
    path = tmp_path/f'master.{extension}'
    export_audio(audio,str(path),44100,subtype,ceiling=-1)
    read = decode(str(path))
    assert read.rate == 44100
    assert abs(read.duration-audio.duration) < .001
    assert true_peak(read.samples) < .892


def test_protect_original(tmp_path):
    audio = tone()
    audio.path = str(tmp_path/'original.wav')
    with pytest.raises(AudioError, match='original_protected'):
        export_audio(audio, audio.path, audio.rate)


def test_cancellation():
    progress = Progress()
    progress.event.set()
    with pytest.raises(Cancelled):
        analyze(tone(), progress=progress)


def test_history(tmp_path, tonal_result):
    path = tmp_path/'history.json'
    history = History(path)
    history.add('source.wav',tonal_result)
    restored = History(path)
    assert len(restored.entries) == 1
    assert 'spectrogram' not in restored.entries[0]['result']
    restored.remove(restored.entries[0]['id'])
    assert History(path).entries == []


def test_localization_parity():
    tr = Translator()
    assert tr.catalogs['en'].keys() == tr.catalogs['ru'].keys()
    assert tr('play') == 'Play'
    tr.language = 'ru'
    assert tr('play') == 'Играть'


def test_antiphase_stereo_does_not_become_silence():
    audio = tone(duration=1)
    audio.samples = np.column_stack((audio.samples[:, 0], -audio.samples[:, 0]))
    result = analyze(audio)
    assert abs(result['dominant']-440) < 2
    assert 'silence' not in result['warnings']


def test_selection_frequency():
    a, b = tone(220, 1), tone(880, 1)
    audio = Audio(np.concatenate((a.samples,b.samples)), a.rate, 'selection.wav')
    result = analyze(audio, 1, 2)
    assert abs(result['dominant']-880) < 2


def test_invalid_settings():
    with pytest.raises(AudioError, match='invalid_settings'):
        master(tone(), MasterSettings(width=float('nan')))


def test_cancellation_mid_analysis():
    progress = Progress()
    progress.callback = lambda value, stage: progress.event.set() if value >= 8 else None
    with pytest.raises(Cancelled):
        analyze(tone(), progress=progress)
