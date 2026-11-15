from __future__ import annotations

import math
import os
from pathlib import Path
import subprocess
import tempfile

import imageio_ffmpeg
import numpy as np
import soundfile as sf
from scipy.signal import resample_poly

from .core import Audio, AudioError, Progress

MAX_FRAMES = 48_000 * 60 * 45


def ffmpeg() -> str:
    return imageio_ffmpeg.get_ffmpeg_exe()


def run_codec(args: list[str], progress: Progress):
    with tempfile.TemporaryFile() as err:
        process = subprocess.Popen([ffmpeg(), '-nostdin', '-hide_banner', '-loglevel', 'error', *args],
                                   stdout=subprocess.DEVNULL, stderr=err,
                                   creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        try:
            while True:
                progress.check()
                try:
                    code = process.wait(timeout=0.1)
                    break
                except subprocess.TimeoutExpired:
                    continue
            if code:
                raise AudioError('codec_error')
        finally:
            if process.poll() is None:
                process.kill()
                process.wait()


def read_sound(path: str, progress: Progress) -> tuple[np.ndarray, int]:
    with sf.SoundFile(path) as source:
        if source.channels not in (1, 2):
            raise AudioError('channels_error')
        if source.frames > MAX_FRAMES or source.frames * source.channels * 4 > 512 * 1024**2:
            raise AudioError('too_large')
        if source.samplerate < 8000 or source.samplerate > 192000:
            raise AudioError('rate_error')
        samples = np.empty((source.frames, source.channels), dtype=np.float32)
        for pos in range(0, source.frames, 262144):
            progress.update(int(85 * pos / max(1, source.frames)), 'decoding')
            block = source.read(min(262144, source.frames - pos), dtype='float32', always_2d=True)
            samples[pos:pos + len(block)] = block
        return samples, source.samplerate


def decode(path: str, progress: Progress | None = None) -> Audio:
    progress = progress or Progress()
    progress.check()
    if not Path(path).is_file():
        raise AudioError('missing_file')
    try:
        samples, rate = read_sound(path, progress)
    except (sf.LibsndfileError, RuntimeError):
        with tempfile.TemporaryDirectory(prefix='keywave-decode-') as temp:
            wav = str(Path(temp) / 'decoded.wav')
            # Cap decoded output; overflow is rejected, never silently truncated.
            run_codec(['-i', path, '-map', '0:a:0', '-vn', '-t', '2701', '-c:a', 'pcm_f32le', wav], progress)
            samples, rate = read_sound(wav, progress)
    if len(samples) < rate // 10:
        raise AudioError('too_short')
    if not np.isfinite(samples).all():
        raise AudioError('invalid_audio')
    progress.update(100, 'ready')
    return Audio(samples, rate, str(Path(path).resolve()))


def resample(samples: np.ndarray, source: int, target: int) -> np.ndarray:
    if source == target:
        return samples.copy()
    divisor = math.gcd(source, target)
    return resample_poly(samples, target // divisor, source // divisor, axis=0).astype(np.float32)


def export_audio(audio: Audio, path: str, rate: int, subtype: str = 'PCM_24',
                 bitrate: int = 320, progress: Progress | None = None, ceiling: float | None = None):
    progress = progress or Progress()
    dest = Path(path).resolve()
    if dest == Path(audio.path).resolve():
        raise AudioError('original_protected')
    if rate not in (22050, 32000, 44100, 48000, 88200, 96000, 192000):
        raise AudioError('invalid_settings')
    if dest.suffix.lower() not in ('.wav', '.flac', '.mp3'):
        raise AudioError('unsupported')
    progress.update(5, 'resampling')
    samples = resample(audio.samples, audio.rate, rate)
    progress.update(25, 'exporting')
    if ceiling is not None:
        from .mastering import true_peak
        peak = true_peak(samples)
        samples *= min(1., 10 ** (ceiling / 20) / max(peak, 1e-12))
    if subtype != 'FLOAT':
        bits = 16 if subtype == 'PCM_16' else 24
        rng = np.random.default_rng()
        # TPDF dither is noise added for quantization, never an analysis result.
        samples += ((rng.random(samples.shape) - rng.random(samples.shape)) / 2**(bits-1)).astype(np.float32)
        samples = np.clip(samples, -1, 1 - 2**(1-bits))
    fd, temporary = tempfile.mkstemp(suffix=dest.suffix, dir=dest.parent)
    os.close(fd)
    try:
        if dest.suffix.lower() == '.mp3':
            with tempfile.TemporaryDirectory(prefix='keywave-export-') as temp:
                wav = str(Path(temp) / 'master.wav')
                sf.write(wav, samples, rate, subtype='FLOAT')
                run_codec(['-y', '-i', wav, '-codec:a', 'libmp3lame', '-b:a', f'{bitrate}k', temporary], progress)
        else:
            sf.write(temporary, samples, rate, subtype='PCM_24' if dest.suffix.lower() == '.flac' and subtype == 'FLOAT' else subtype)
        progress.update(95, 'exporting')
        os.replace(temporary, dest)
        progress.update(100, 'exported')
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def waveform(samples: np.ndarray, count: int = 2400):
    mono = samples.mean(axis=1)
    step = max(1, int(np.ceil(len(mono) / count)))
    starts = np.arange(0, len(mono), step)
    return starts, np.minimum.reduceat(mono, starts), np.maximum.reduceat(mono, starts)
