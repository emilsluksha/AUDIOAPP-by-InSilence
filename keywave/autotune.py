"""Offline monophonic pitch correction: pYIN tracking and time-varying TD-PSOLA.

This is a dry-vocal processor, not a polyphonic source separator or an Antares clone.
Pitch-synchronous grains retain their original duration to approximately retain
the vocal spectral envelope. Unvoiced spans are copied, not transposed.
"""
from dataclasses import dataclass
import numpy as np
import librosa
from scipy.ndimage import median_filter

from .audio import resample
from .core import Audio, AudioError, Progress

SCALES = {'minor': (0, 2, 3, 5, 7, 8, 10), 'major': (0, 2, 4, 5, 7, 9, 11), 'chromatic': tuple(range(12))}
VOCAL_PRESETS = {
    'natural_vocal': (.45, 'natural', .8), 'soft_tune': (.65, 'natural', .5),
    'melodic_rap': (.85, 'fast', .25), 'hard_trap': (1., 'fast', .1),
    'hyperpop': (1., 'instant', .05), 'robotic_tune': (1., 'instant', 0.),
}


@dataclass
class TuneSettings:
    root: int = 5
    scale: str = 'minor'
    bpm: float = 139.
    strength: float = .65
    retune: str = 'natural'
    humanize: float = .5
    preserve_formants: bool = True

    def validate(self):
        if (self.root not in range(12) or self.scale not in SCALES or self.retune not in ('natural','fast','instant')
            or not np.isfinite([self.bpm,self.strength,self.humanize]).all()
            or not 40 <= self.bpm <= 300 or not 0 <= self.strength <= 1 or not 0 <= self.humanize <= 1):
            raise AudioError('invalid_settings')


def target_notes(midi: np.ndarray, root: int, scale: str) -> np.ndarray:
    allowed = np.array([note for note in range(12, 121) if (note-root) % 12 in SCALES[scale]])
    return allowed[np.argmin(np.abs(midi[:,None]-allowed[None,:]), axis=1)].astype(float)


def correction_curve(f0: np.ndarray, settings: TuneSettings, step: float) -> tuple[np.ndarray, np.ndarray]:
    valid = np.isfinite(f0) & (f0 > 0)
    target = np.full(len(f0), np.nan)
    corrected = f0.copy()
    if not valid.any():
        return corrected, target
    midi = np.full(len(f0), np.nan)
    midi[valid] = librosa.hz_to_midi(f0[valid])
    target[valid] = target_notes(midi[valid], settings.root, settings.scale)
    # Suppress one-frame note flips; never filter across unvoiced boundaries.
    for begin, end in voiced_runs(valid):
        if end-begin >= 3:
            target[begin:end] = median_filter(target[begin:end], size=3, mode='nearest')
        smooth = midi[begin]
        held = 0.
        for i in range(begin, end):
            held = held+step if i > begin and target[i] == target[i-1] else 0.
            time_constant = {'natural': .12, 'fast': .025, 'instant': 0.}[settings.retune]
            time_constant *= 1+settings.humanize*min(held/.3, 1)*2
            amount = settings.strength*(1-settings.humanize*.35*min(held/.3, 1))
            desired = midi[i] + amount*(target[i]-midi[i])
            alpha = 1. if time_constant == 0 else 1-np.exp(-step/time_constant)
            smooth += alpha*(desired-smooth)
            corrected[i] = librosa.midi_to_hz(smooth)
    return corrected, target


def voiced_runs(valid):
    edges = np.diff(np.r_[False, valid, False].astype(np.int8))
    return list(zip(np.where(edges == 1)[0], np.where(edges == -1)[0]))


def track_pitch(audio: Audio, progress: Progress):
    channel = int(np.argmax(np.mean(audio.samples.astype(np.float64)**2,axis=0)))
    mono = audio.samples[:,channel]
    rate, hop = 16000, 160
    y = resample(mono, audio.rate, rate)
    chunk, padding = rate*6, rate//5
    time_parts, f0_parts, prob_parts = [], [], []
    for offset in range(0,len(y),chunk):
        progress.update(5+int(48*offset/max(len(y),1)), 'vocal_tracking')
        begin, end = max(0,offset-padding), min(len(y),offset+chunk+padding)
        part = y[begin:end]
        if np.max(np.abs(part)) < 1e-5:
            times = np.arange(offset,min(offset+chunk,len(y)),hop)/rate
            f0, probability = np.full(len(times),np.nan), np.zeros(len(times))
        else:
            f0, voiced, probability = librosa.pyin(part, sr=rate, fmin=65, fmax=1000,
                frame_length=1024, hop_length=hop, resolution=.1, fill_na=np.nan)
            times = (begin+np.arange(len(f0))*hop)/rate
            keep = (times >= offset/rate) & (times < min(offset+chunk,len(y))/rate)
            f0[~voiced | (probability < .15)] = np.nan
            times, f0, probability = times[keep], f0[keep], probability[keep]
        time_parts.append(times)
        f0_parts.append(f0)
        prob_parts.append(probability)
        progress.check()
    return np.concatenate(time_parts), np.concatenate(f0_parts), np.concatenate(prob_parts), channel


def psola(samples, rate, times, f0, corrected, channel, preserve_formants, progress):
    result = samples.copy()
    valid = np.isfinite(f0) & np.isfinite(corrected)
    runs = voiced_runs(valid)
    for run_index, (first, last) in enumerate(runs):
        progress.update(55+int(39*run_index/max(1,len(runs))), 'vocal_correcting')
        begin = max(0,int(times[first]*rate))
        end = min(len(samples),int((times[last-1]+.01)*rate))
        if end-begin < rate*.06:
            continue
        track_times = times[first:last]*rate
        source_pitch = f0[first:last]
        target_pitch = corrected[first:last]
        # Analysis epochs: phase-consistent peaks near each predicted pitch period.
        mono = samples[:,channel]
        period = rate/source_pitch[0]
        search_end = min(end,begin+int(period*2))
        position = begin+int(np.argmax(mono[begin:search_end]))
        epochs = [position]
        while position < end:
            period = rate/float(np.interp(position,track_times,source_pitch))
            predicted = position+period
            lo = max(position+1,int(predicted-.22*period))
            hi = min(end,int(predicted+.22*period)+1)
            if lo >= hi:
                break
            position = lo+int(np.argmax(mono[lo:hi]))
            epochs.append(position)
        epochs = np.asarray(epochs)
        if len(epochs) < 3:
            continue
        acc = np.zeros((end-begin,samples.shape[1]),dtype=np.float64)
        weights = np.zeros(end-begin,dtype=np.float64)
        synthesis = float(epochs[0])
        count = 0
        while synthesis < end:
            if count % 256 == 0:
                progress.check()
            index = int(np.searchsorted(epochs,synthesis))
            index = min(max(index,1),len(epochs)-1)
            epoch = epochs[index-1] if abs(epochs[index-1]-synthesis) < abs(epochs[index]-synthesis) else epochs[index]
            input_hz = float(np.interp(epoch,track_times,source_pitch))
            output_hz = float(np.interp(synthesis,track_times,target_pitch))
            ratio = output_hz/input_hz
            half = max(2,round(rate/input_hz/(1 if preserve_formants else ratio)))
            offsets = np.arange(-half,half+1)
            locations = epoch+offsets*(1 if preserve_formants else ratio)
            destination = round(synthesis)+offsets
            keep = (destination >= begin) & (destination < end) & (locations >= begin) & (locations < end-1)
            locations, destination = locations[keep], destination[keep]-begin
            win = np.hanning(2*half+1)[keep]
            left = locations.astype(int)
            frac = locations-left
            grain = samples[left]*(1-frac[:,None])+samples[left+1]*frac[:,None]
            acc[destination] += grain*win[:,None]
            weights[destination] += win
            synthesis += rate/output_hz
            count += 1
        available = weights > .05
        wet = samples[begin:end].copy()
        wet[available] = (acc[available]/weights[available,None]).astype(np.float32)
        fade = min(round(rate*.015), len(wet)//3)
        blend = np.ones(len(wet),dtype=np.float32)
        blend[:fade] = np.linspace(0,1,fade)
        blend[-fade:] = np.linspace(1,0,fade)
        blend[~available] = 0
        result[begin:end] = samples[begin:end]*(1-blend[:,None])+wet*blend[:,None]
    return result


def tune_vocal(audio: Audio, settings: TuneSettings, progress: Progress | None = None):
    progress = progress or Progress()
    settings.validate()
    progress.check()
    if audio.duration < .5:
        raise AudioError('too_short')
    if settings.strength == 0:
        progress.update(100,'ready')
        return Audio(audio.samples.copy(),audio.rate,audio.path), {'times':[], 'input_hz':[], 'output_hz':[], 'target_midi':[], 'voiced_fraction':0., 'bypass':True}
    times, f0, probability, channel = track_pitch(audio,progress)
    corrected, targets = correction_curve(f0,settings,.01)
    samples = psola(audio.samples,audio.rate,times,f0,corrected,channel,settings.preserve_formants,progress)
    if not np.isfinite(samples).all():
        raise AudioError('invalid_audio')
    peak = float(np.max(np.abs(samples)))
    if peak > .999:
        samples *= .999/peak
    progress.update(100,'ready')
    def nullable(values):
        return [float(v) if np.isfinite(v) else None for v in values]
    return Audio(samples,audio.rate,audio.path), {'times': times.tolist(), 'input_hz':nullable(f0),
        'output_hz':nullable(corrected), 'target_midi':nullable(targets),
        'voiced_fraction':float(np.mean(np.isfinite(f0))), 'bypass':False}
