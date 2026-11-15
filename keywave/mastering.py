from __future__ import annotations

from dataclasses import dataclass
import numpy as np
import pyloudnorm as pyln
from numba import njit
from scipy.ndimage import maximum_filter1d
from scipy.signal import butter, sosfilt, resample_poly

from .core import Audio, AudioError, Progress


def true_peak(samples: np.ndarray) -> float:
    peak = 0.
    # Overlapping blocks retain interpolation context without a full 4x track allocation.
    for start in range(0, len(samples), 262144):
        block = samples[max(0, start-32):start+262144+32]
        peak = max(peak, float(np.max(np.abs(resample_poly(block, 4, 1, axis=0)))))
    return peak


def measure(samples: np.ndarray, rate: int) -> dict:
    peak = true_peak(samples)
    rms = float(np.sqrt(np.mean(samples.astype(np.float64)**2)))
    loudness = pyln.Meter(rate, block_size=min(.4, len(samples)/rate)).integrated_loudness(samples)
    return {'lufs': float(loudness) if np.isfinite(loudness) else None,
            'true_peak': float(20 * np.log10(peak)) if peak > 1e-12 else None,
            'crest': float(20 * np.log10(max(peak, 1e-12) / max(rms, 1e-12)))}


@dataclass
class MasterSettings:
    preset: str = 'balanced'
    intensity: float = .6
    target: float = -14.
    width: float = 1.
    eq: float = .5
    compression: float = .5
    ceiling: float = -1.


PRESETS = {
    'balanced': (-14., 1., .5, .5, [0., 0., 0.]),
    'loud': (-9., 1.05, .4, .85, [0.5, 0., .8]),
    'smooth': (-16., 1., .65, .25, [0., .2, -1.5]),
    'hiphop': (-11., 1.05, .6, .7, [1.2, -.6, .2]),
    'vocal': (-14., .95, .65, .45, [-.5, 1.4, .4]),
    'custom': (-14., 1., .5, .5, [0., 0., 0.]),
}


@njit(cache=True)
def compressor_gain(level, threshold, ratio, attack, release):
    result = np.empty(len(level), dtype=np.float32)
    envelope = 0.
    for i in range(len(level)):
        coefficient = attack if level[i] > envelope else release
        envelope = coefficient * envelope + (1-coefficient) * level[i]
        db = 20 * np.log10(max(envelope, 1e-10))
        over = db - threshold
        knee = 6.
        reduction = 0.
        if over > knee / 2:
            reduction = (1-1/ratio) * over
        elif over > -knee / 2:
            reduction = (1-1/ratio) * (over+knee/2)**2 / (2*knee)
        result[i] = 10**(-reduction/20)
    return result


@njit(cache=True)
def release_gain(target, coefficient, previous):
    out = np.empty(len(target), dtype=np.float32)
    for i in range(len(target)):
        previous = min(target[i], coefficient*previous + (1-coefficient)*target[i])
        out[i] = previous
    return out, previous


def limit(samples: np.ndarray, rate: int, ceiling: float, progress: Progress) -> np.ndarray:
    ceiling_linear = 10 ** (ceiling/20)
    lookahead = max(3, int(rate * .005) | 1)
    level = np.max(np.abs(samples), axis=1)
    envelope = maximum_filter1d(level, lookahead, mode='nearest')
    target = np.minimum(1., ceiling_linear / np.maximum(envelope, 1e-10))
    previous = 1.
    for pos in range(0, len(samples), 262144):
        progress.check()
        gain, previous = release_gain(target[pos:pos+262144], np.exp(-1/(rate*.08)), previous)
        samples[pos:pos+len(gain)] *= gain[:, None]
    peak = true_peak(samples)
    samples *= min(1., ceiling_linear / max(peak, 1e-12))
    return samples


def master(audio: Audio, settings: MasterSettings, progress: Progress | None = None):
    progress = progress or Progress()
    values = [settings.intensity, settings.target, settings.width, settings.eq, settings.compression, settings.ceiling]
    if (not np.isfinite(values).all() or settings.preset not in PRESETS or
        not 0 <= settings.intensity <= 1 or not -24 <= settings.target <= -6 or
        not 0 <= settings.width <= 1.5 or not 0 <= settings.eq <= 1 or
        not 0 <= settings.compression <= 1 or not -3 <= settings.ceiling <= -.1):
        raise AudioError('invalid_settings')
    progress.update(3, 'measuring')
    before = measure(audio.samples, audio.rate)
    if before['lufs'] is None:
        raise AudioError('silence')
    x = audio.samples.copy()
    sr = audio.rate
    intensity = settings.intensity
    progress.update(15, 'equalizing')
    highpass = butter(2, 25, fs=sr, btype='highpass', output='sos')
    filtered = sosfilt(highpass, x, axis=0).astype(np.float32)
    x += intensity * (filtered-x)
    low = sosfilt(butter(2, 180, fs=sr, output='sos'), x, axis=0).astype(np.float32)
    high = sosfilt(butter(2, min(4000, sr*.4), fs=sr, btype='highpass', output='sos'), x, axis=0).astype(np.float32)
    mid = x - low - high
    energies = np.array([np.mean(band**2) for band in (low, mid, high)])
    reference = np.array([.35, .5, .15])
    balance = energies / max(float(energies.sum()), 1e-12)
    corrections = np.clip(10 * np.log10(reference / np.maximum(balance, 1e-8)), -2., 2.)
    corrections += np.asarray(PRESETS[settings.preset][4])
    gains = 10 ** (corrections * settings.eq * intensity / 20)
    x = (low*gains[0] + mid*gains[1] + high*gains[2]).astype(np.float32)
    del low, mid, high, filtered
    progress.update(32, 'compressing')
    amount = settings.compression * intensity
    gain = compressor_gain(np.max(np.abs(x), axis=1), -18., 1+3*amount,
                           np.exp(-1/(sr*.01)), np.exp(-1/(sr*.12)))
    x *= gain[:, None]
    if x.shape[1] == 2:
        mid = (x[:, 0]+x[:, 1])*.5
        side = (x[:, 0]-x[:, 1])*.5 * (1 + (settings.width-1)*intensity)
        x[:, 0], x[:, 1] = mid+side, mid-side
    progress.update(52, 'normalizing')
    current = measure(x, sr)['lufs']
    # Intensity zero is a true bypass; full intensity reaches the chosen loudness request.
    requested = before['lufs'] + intensity * (settings.target-before['lufs'])
    if current is not None:
        x *= 10 ** (np.clip(requested-current, -30, 30) / 20)
    progress.update(70, 'limiting')
    if intensity > 0:
        x = limit(x, sr, settings.ceiling, progress)
    if not np.isfinite(x).all():
        raise AudioError('invalid_audio')
    progress.update(90, 'measuring')
    after = measure(x, sr)
    progress.update(100, 'ready')
    return Audio(x, sr, audio.path), {'before': before, 'after': after, 'requested_lufs': requested,
                                     'target_limited': abs(after['lufs'] - requested) > 1,
                                     'eq_db': (corrections*settings.eq*intensity).tolist()}
