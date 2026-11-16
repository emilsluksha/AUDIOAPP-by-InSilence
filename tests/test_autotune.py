import numpy as np
import librosa
import pytest
from keywave.autotune import TuneSettings, tune_vocal, correction_curve, target_notes, VOCAL_PRESETS
from keywave.core import Audio, AudioError, Progress, Cancelled


def vocal(frequencies=(280.,430.), seconds=1.3):
    sr = 22050
    pieces = []
    for hz in frequencies:
        t = np.arange(round(sr*seconds))/sr
        pieces.append((.15*np.sin(2*np.pi*hz*t)+.04*np.sin(4*np.pi*hz*t)).astype(np.float32))
    return Audio(np.concatenate(pieces)[:,None],sr,'vocal.wav')


def pitch(samples,sr):
    return float(np.median(librosa.yin(samples,fmin=100,fmax=700,sr=sr)))


def test_dynamic_notes_and_duration():
    audio = vocal()
    output,report = tune_vocal(audio,TuneSettings(root=0,scale='major',strength=1,retune='instant',humanize=0))
    assert output.samples.shape == audio.samples.shape
    assert np.isfinite(output.samples).all()
    sr = audio.rate
    assert abs(pitch(output.samples[int(.4*sr):sr,0],sr)-293.6648) < 3
    assert abs(pitch(output.samples[int(1.7*sr):int(2.3*sr),0],sr)-440.) < 3
    assert report['voiced_fraction'] > .8


def test_zero_strength_exact_bypass():
    audio = vocal()
    output,report = tune_vocal(audio,TuneSettings(strength=0))
    np.testing.assert_array_equal(audio.samples,output.samples)
    assert report['bypass']


def test_strength_and_retune_are_independent():
    f0 = np.full(120,280.)
    instant,_ = correction_curve(f0,TuneSettings(root=0,scale='major',strength=1,retune='instant',humanize=0),.01)
    natural,_ = correction_curve(f0,TuneSettings(root=0,scale='major',strength=1,retune='natural',humanize=0),.01)
    half,_ = correction_curve(f0,TuneSettings(root=0,scale='major',strength=.5,retune='instant',humanize=0),.01)
    assert natural[0] < instant[0]
    assert abs(natural[-1]-instant[-1]) < .1
    assert 280 < half[-1] < instant[-1]


def test_scales_and_tempo_do_not_transpose():
    assert target_notes(np.array([63.]),0,'minor')[0] == 63
    assert target_notes(np.array([63.]),0,'major')[0] != 63
    assert target_notes(np.array([63.]),0,'chromatic')[0] == 63
    f0 = np.full(40,280.)
    a,_ = correction_curve(f0,TuneSettings(bpm=40),.01)
    b,_ = correction_curve(f0,TuneSettings(bpm=300),.01)
    np.testing.assert_array_equal(a,b)
    assert len(set(VOCAL_PRESETS.values())) == 6


def test_silence_and_cancel():
    audio = Audio(np.zeros((22050,1),dtype=np.float32),22050,'silence.wav')
    output,report = tune_vocal(audio,TuneSettings())
    np.testing.assert_array_equal(output.samples,audio.samples)
    assert report['voiced_fraction'] == 0
    progress = Progress()
    progress.event.set()
    with pytest.raises(Cancelled):
        tune_vocal(audio,TuneSettings(),progress)


def test_unvoiced_noise_is_retained():
    audio = Audio(np.random.default_rng(7).normal(0,.03,(22050,1)).astype(np.float32),22050,'noise.wav')
    output,report = tune_vocal(audio,TuneSettings(strength=1))
    assert report['voiced_fraction'] < .05
    np.testing.assert_allclose(output.samples,audio.samples,atol=1e-6)


@pytest.mark.parametrize('settings',[TuneSettings(bpm=301),TuneSettings(root=12),TuneSettings(strength=float('nan'))])
def test_invalid_tune_settings(settings):
    with pytest.raises(AudioError):
        tune_vocal(vocal(),settings)
