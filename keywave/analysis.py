from __future__ import annotations

import numpy as np
import librosa
from scipy.signal import find_peaks, welch

from .core import Audio, AudioError, Progress
from .audio import resample
from .mastering import measure

NOTES = ['C', 'C#', 'D', 'Eb', 'E', 'F', 'F#', 'G', 'Ab', 'A', 'Bb', 'B']
MAJOR = np.array([6.35, 2.23, 3.48, 2.33, 4.38, 4.09, 2.52, 5.19, 2.39, 3.66, 2.29, 2.88])
MINOR = np.array([6.33, 2.68, 3.52, 5.38, 2.60, 3.53, 2.54, 4.75, 3.98, 2.69, 3.34, 3.17])
CAMELOT_MAJOR = [8, 3, 10, 5, 12, 7, 2, 9, 4, 11, 6, 1]
CAMELOT_MINOR = [5, 12, 7, 2, 9, 4, 11, 6, 1, 8, 3, 10]


def key_scores(chroma: np.ndarray) -> list[dict]:
    distribution = np.mean(chroma, axis=1) if chroma.ndim == 2 else chroma
    scores = []
    for minor, profile in ((False, MAJOR), (True, MINOR)):
        for root in range(12):
            correlation = np.corrcoef(distribution, np.roll(profile, root))[0, 1] if np.std(distribution) > 1e-8 else 0
            scores.append({'root': NOTES[root], 'minor': minor, 'score': float(correlation),
                           'camelot': str((CAMELOT_MINOR if minor else CAMELOT_MAJOR)[root]) + ('A' if minor else 'B'),
                           'relative': NOTES[(root + (3 if minor else 9)) % 12]})
    return sorted(scores, key=lambda item: item['score'], reverse=True)


def analyze(audio: Audio, start: float = 0, end: float | None = None,
            quality: str = 'full', progress: Progress | None = None) -> dict:
    progress = progress or Progress()
    end = audio.duration if end is None else min(end, audio.duration)
    if start < 0 or end - start < 0.5:
        raise AudioError('too_short')
    segment = audio.samples[int(start * audio.rate):int(end * audio.rate)]
    progress.update(3, 'preparing')
    # Use the loudest channel for anti-phase stereo instead of cancelling to silence.
    channel = int(np.argmax(np.mean(segment.astype(np.float64)**2, axis=0)))
    y = resample(segment[:, channel], audio.rate, 22050)
    sr = 22050
    warnings = []
    if np.max(np.abs(y)) < 1e-5:
        return {'key': None, 'candidates': [], 'bpm': None, 'tempo_confidence': 0., 'confidence': 0.,
                'dominant': None, 'pitch': None, 'chroma': [0.] * 12, 'warnings': ['silence'],
                'start': start, 'end': end, 'rate': audio.rate, 'metrics': measure(segment, audio.rate),
                'frequency': [], 'spectrum': [], 'spectrogram': [], 'peaks': [], 'key_windows': []}
    # Process bounded windows; retain coverage across the whole selection in quick mode.
    hop = 512
    chunk = sr * 24
    starts = list(range(0, len(y), chunk))
    if quality == 'quick' and len(starts) > 4:
        starts = [starts[i] for i in np.linspace(0, len(starts)-1, 4).astype(int)]
        warnings.append('sampled_analysis')
    chromas, onset_parts, pitches, windows, specs = [], [], [], [], []
    harmonic_energy = total_energy = 0.
    for index, offset in enumerate(starts):
        progress.update(8 + int(65 * index / len(starts)), 'harmonic_analysis')
        part = y[offset:offset + chunk]
        if len(part) < 4096:
            continue
        harmonic, percussive = librosa.effects.hpss(part)
        progress.check()
        chroma = librosa.feature.chroma_cqt(y=harmonic, sr=sr, hop_length=hop, n_octaves=6)
        chromas.append(chroma)
        harmonic_energy += float(np.sum(harmonic**2))
        total_energy += float(np.sum(part**2))
        ranked = key_scores(chroma)
        windows.append({'time': start + offset/sr, 'root': ranked[0]['root'], 'minor': ranked[0]['minor']})
        onset_parts.append(librosa.onset.onset_strength(y=percussive, sr=sr, hop_length=hop))
        magnitude = np.abs(librosa.stft(part, n_fft=2048, hop_length=1024))
        specs.append(magnitude[:, ::max(1, magnitude.shape[1] // 120)])
        # YIN plus periodicity gate: estimate only frames resembling a single periodic source.
        f0 = librosa.yin(harmonic, fmin=65, fmax=1600, sr=sr, frame_length=2048, hop_length=1024)
        flat = librosa.feature.spectral_flatness(y=harmonic, n_fft=2048, hop_length=1024)[0]
        rms = librosa.feature.rms(y=harmonic, frame_length=2048, hop_length=1024)[0]
        valid = (flat < .02) & (rms > max(float(np.max(rms)) * .2, 1e-5))
        pitches.extend(f0[valid].tolist())
        progress.check()
    if not chromas:
        raise AudioError('too_short')
    merged = np.concatenate(chromas, axis=1)
    distribution = merged.mean(axis=1)
    candidates = key_scores(distribution)
    best = candidates[0]
    margin = best['score'] - candidates[1]['score']
    confidence = float(np.clip(max(0., best['score']) * .65 + margin * 1.8, 0, 1))
    concentration = float(np.max(distribution) / max(np.sum(distribution), 1e-9))
    tonal = harmonic_energy / max(total_energy, 1e-9) > .12 and best['score'] > .45 and concentration < .65
    key = best if tonal else None
    if not tonal:
        warnings.append('no_key')
    elif confidence < .65 or margin < .08:
        warnings.append('ambiguous_key')
    if len({(item['root'], item['minor']) for item in windows}) > 1:
        warnings.append('changing_key')
    progress.update(78, 'tempo_analysis')
    tempos, confidences = [], []
    for onset in onset_parts:
        if len(onset) < 16 or np.max(onset) < 1e-5:
            continue
        tempo, beats = librosa.beat.beat_track(onset_envelope=onset, sr=sr, hop_length=hop, trim=False)
        value = float(np.asarray(tempo).ravel()[0])
        if value <= 0 or len(beats) < 3:
            continue
        intervals = np.diff(beats)
        if len(beats) >= 5 and np.std(intervals) / max(np.mean(intervals), 1) < .15:
            fitted_period = float(np.polyfit(np.arange(len(beats)), beats, 1)[0])
            value = 60 * sr / (hop * fitted_period)
        lag = round(60 * sr / (hop * value))
        centered = onset - onset.mean()
        periodicity = float(np.dot(centered[:-lag], centered[lag:]) / max(np.dot(centered, centered), 1e-9)) if lag < len(centered) else 0
        tempos.append(value)
        confidences.append(float(np.clip(periodicity, 0, 1)))
    bpm = float(np.median(tempos)) if tempos and max(confidences) > .12 else None
    tempo_confidence = float(np.mean(confidences)) if confidences else 0.
    if bpm is None or tempo_confidence < .45:
        warnings.append('uncertain_tempo')
    if len(tempos) > 1 and np.std(tempos) > 4:
        warnings.append('changing_tempo')
    progress.update(87, 'frequency_analysis')
    freq, power = welch(segment[:, channel], audio.rate, nperseg=min(32768, len(segment)))
    db = 10 * np.log10(np.maximum(power, 1e-16))
    peak_indices, _ = find_peaks(db, prominence=6)
    peak_indices = sorted(peak_indices, key=lambda i: power[i], reverse=True)[:8]
    dominant = float(freq[np.argmax(power)])
    pitch = None
    if len(pitches) > 5:
        midi = librosa.hz_to_midi(np.asarray(pitches))
        if np.percentile(midi, 75) - np.percentile(midi, 25) < 1.5:
            hz = float(np.median(pitches))
            fundamental = power[np.abs(freq-hz) < max(6., hz*.015)]
            # Reject subharmonic YIN estimates when no fundamental is actually present.
            if len(fundamental) and float(np.max(fundamental)) > float(np.max(power))*.1:
                pitch = {'hz': hz, 'note': librosa.midi_to_note(int(round(librosa.hz_to_midi(hz))))}
    spectrum = np.concatenate(specs, axis=1)
    spectrum = spectrum[:, ::max(1, int(np.ceil(spectrum.shape[1]/900)))]
    spectrum = librosa.amplitude_to_db(spectrum, ref=np.max)
    progress.update(93, 'measuring')
    metrics = measure(segment, audio.rate)
    progress.update(100, 'ready')
    return {'key': key, 'candidates': candidates[:3] if tonal else [], 'confidence': confidence if tonal else 0.,
            'bpm': bpm, 'tempo_confidence': tempo_confidence, 'dominant': dominant, 'pitch': pitch,
            'chroma': (distribution / max(float(distribution.sum()), 1e-9)).tolist(), 'warnings': warnings,
            'start': start, 'end': end, 'rate': audio.rate, 'metrics': metrics, 'frequency': freq.tolist(),
            'spectrum': db.tolist(), 'spectrogram': spectrum.astype(np.float32).tolist(),
            'peaks': [float(freq[i]) for i in peak_indices], 'key_windows': windows}
